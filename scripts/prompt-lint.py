#!/usr/bin/env python3
# =============================================================================
# script: prompt-lint.py
# purpose: Deterministic, ZERO-TOKEN linter that validates a prompt against
#          Anthropic's "Prompting best practices" doc BEFORE it is ever sent to
#          Claude. Pure static analysis (stdlib only) - it never calls an LLM,
#          so the gate itself costs nothing. Powers a Claude Code
#          UserPromptSubmit hook, a `claude-lint` CLI facade, and a --watch
#          terminal intellisense mode.
# inputs:
#   [FILE]                 prompt file to lint (or read stdin, or -c TEXT)
#   -c, --content TEXT     lint literal text instead of a file
#   --format human|json    output shape (default: human; json for hooks/tools)
#   --config PATH          config file (default: search .promptlintrc.json +
#                          ~/.config/promptlint/config.json)
#   --role user|system|assistant   which role the text plays (gates some rules)
#   --fail-on off|info|warn|error  exit-nonzero threshold (default from config)
#   --select / --ignore ID,ID      ad-hoc enable/disable rules
#   --watch                live re-lint on file change (terminal intellisense)
#   --list-rules           print the full rule catalog and exit
#   --explain RULE_ID      print one rule's rationale + doc anchor and exit
#   --no-color             disable ANSI
# outputs:
#   human: annotated findings to stdout; summary to stderr
#   json:  {"ok":bool,"counts":{...},"findings":[...]} to stdout
#   exit:  0 = clean (below fail-on); 1 = findings at/above fail-on; 2 = usage
# touches-secrets: no
# when-to-use:    validate/lint any prompt before spending tokens; CI for prompt
#                 files; Claude Code UserPromptSubmit gate; live authoring.
# when-NOT-to-use: you want a semantic/LLM judgement of prompt quality (this is
#                 deterministic only, by design).
# added: 2026-07-05
# family: prompt-lint
# environment: cross-python
# =============================================================================
"""Deterministic prompt linter for Anthropic prompting best practices.

Reference: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices

Design notes
------------
* stdlib only. Fast to import, safe to run from a hook on every prompt.
* Rules are data: each Rule has an id, default severity, doc anchor, and a
  pure check() that yields Findings. Severity is resolved against config so any
  rule can be turned off / up / down without touching code.
* Inline suppression (eslint-style) is honored:
    promptlint-disable-file                 - skip the whole prompt
    promptlint-disable rule-a, rule-b       - skip listed rules for the prompt
    promptlint-disable-line rule-a          - skip on the same line
  (placed anywhere, in any comment style; bare `promptlint-disable` = all rules)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from typing import Callable, Iterable, Iterator

DOC_URL = "https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices"
CURSOR_DOC_URL = "https://cursor.com/docs/agent/prompting"

# Per-target presets: disable irrelevant rules, enable target-specific ones.
PRESETS: dict[str, dict] = {
    "claude": {
        "doc_url": DOC_URL,
        "rules": {
            "thinking/prescriptive-steps": "off",
            "agentic/overengineering-guard": "off",
        },
    },
    "cursor": {
        "doc_url": CURSOR_DOC_URL,
        "rules": {
            # Claude-only mechanics
            "format/prefill-detected": "off",
            "format/preamble-prefill": "off",
            "model/deprecated-model-ref": "off",
            "examples/untagged-example": "off",
            "examples/few-shot-count": "off",
            "role/no-role": "off",
            "thinking/prescriptive-steps": "off",
            "xml/missing-structure": "off",
            "xml/inconsistent-tag-style": "off",
            "longctx/no-document-tags": "off",
            "longctx/no-quote-grounding": "off",
            "longctx/query-not-at-end": "info",
            # Cursor agent defaults
            "agentic/overengineering-guard": "warn",
            "cursor/claude-xml-tags": "warn",
            "cursor/file-without-at": "info",
            "cursor/rules-in-prompt": "info",
            "cursor/plan-without-boundary": "info",
        },
    },
}
PROFILE_ALIASES = {
    "anthropic-best-practices": "claude",
    "cursor-agent": "cursor",
}

# --- severity model ----------------------------------------------------------
SEVERITIES = ("off", "info", "warn", "error")
SEV_RANK = {s: i for i, s in enumerate(SEVERITIES)}


def sev_ge(a: str, b: str) -> bool:
    return SEV_RANK.get(a, 0) >= SEV_RANK.get(b, 0)


# --- data model --------------------------------------------------------------
@dataclass
class Finding:
    rule_id: str
    severity: str          # resolved severity (info|warn|error)
    title: str
    message: str           # what's wrong, in context
    fix: str               # concrete suggested rewrite/action
    line: int = 0          # 1-based; 0 = whole-prompt
    col: int = 0
    doc_anchor: str = ""
    doc_url: str = ""

    def doc_link(self) -> str:
        base = self.doc_url or DOC_URL
        return f"{base}#{self.doc_anchor}" if self.doc_anchor else base


@dataclass
class Rule:
    id: str
    default: str           # default severity
    title: str
    rationale: str         # shown by --explain
    doc_anchor: str
    check: Callable[["Doc"], Iterable[Finding]] = field(repr=False, default=None)


# --- the parsed prompt -------------------------------------------------------
class Doc:
    """Pre-computed views of the prompt so rules don't re-scan repeatedly."""

    def __init__(self, text: str, role: str = "user"):
        self.text = text
        self.role = role
        self.lines = text.splitlines()
        self.lower = text.lower()
        self.words = re.findall(r"\b[\w']+\b", text)
        self.n_words = len(self.words)
        self.n_chars = len(text)
        self.est_tokens = max(1, round(self.n_chars / 4))
        # code-fence-stripped view (so XML-in-code-samples doesn't trip XML rules)
        self.code_stripped = _strip_code(text)
        self.tags = _scan_tags(self.code_stripped)

    def line_of(self, index: int) -> int:
        return self.text.count("\n", 0, index) + 1


# --- helpers -----------------------------------------------------------------
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
# A "structural" tag: '<' immediately followed by a letter (so `< 0.7`, `<=`,
# `a<b` do NOT match), optional '/', name, optional attrs, optional self-close.
_TAG_RE = re.compile(r"<(/?)([A-Za-z][\w-]*)((?:\s[^<>]*?)?)(/?)>")
# Void/HTML tags we never treat as structural prompt scaffolding.
_VOID_TAGS = {"br", "hr", "img", "input", "meta", "link", "wbr", "col", "area",
              "base", "source", "track", "embed", "param"}


def _strip_code(text: str) -> str:
    text = _FENCE_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    text = _INLINE_CODE_RE.sub(" ", text)
    return text


@dataclass
class TagHit:
    name: str
    closing: bool
    selfclose: bool
    index: int
    line: int


def _scan_tags(code_stripped: str) -> list[TagHit]:
    hits: list[TagHit] = []
    for m in _TAG_RE.finditer(code_stripped):
        name = m.group(2).lower()
        if name in _VOID_TAGS:
            continue
        line = code_stripped.count("\n", 0, m.start()) + 1
        hits.append(TagHit(
            name=name,
            closing=bool(m.group(1)),
            selfclose=bool(m.group(4)),
            index=m.start(),
            line=line,
        ))
    return hits


def _find_line(doc: Doc, pattern: str, flags=re.I) -> int:
    m = re.search(pattern, doc.text, flags)
    return doc.line_of(m.start()) if m else 0


# Word lists reused across rules.
_CREATE_VERBS = r"\b(create|make|build|write|implement|generate|design|develop|add|do|help( me)?)\b"
_FORMAT_WORDS = (r"\b(format|json|yaml|xml|markdown|table|csv|bullet|list|schema|"
                 r"tag|section|paragraph|prose|word[s]?|sentence[s]?|length|tone|"
                 r"style|heading|column|field|enum|structure[d]?)\b")
_REASON_WORDS = r"\b(because|since|so that|so as|in order|otherwise|as it|to ensure|to avoid|reason)\b"
_PROHIBITION_RE = re.compile(r"(\bNEVER\b|\bALWAYS\b|\bdo not\b|\bdon'?t\b|\bavoid\b|\bnever\b)")
_SEQ_WORDS = r"\b(first|second|third|then|next|after that|afterwards|finally|lastly|step \d)\b"


# =============================================================================
# RULES
# =============================================================================
def r_vague_task(doc: Doc) -> Iterator[Finding]:
    if doc.role == "system":
        return
    if doc.n_words > 30:
        return
    if not re.search(_CREATE_VERBS, doc.text, re.I):
        return
    has_specifics = (
        re.search(_FORMAT_WORDS, doc.text, re.I)
        or re.search(r"\b(include|with|using|that|which|so that|for)\b", doc.text, re.I)
        or re.search(r"\d", doc.text)
    )
    if has_specifics:
        return
    yield Finding(
        "clarity/vague-task", "", "Vague task with no specifics",
        "The task is short and gives no output format, constraints, or detail. "
        "Claude is 'a brilliant new employee' - it cannot infer your norms.",
        "Be specific and request above-and-beyond work, e.g. add 'Include as "
        "many relevant features as possible. Go beyond the basics to create a "
        "fully-featured implementation.' State the desired output format and constraints.",
        line=_find_line(doc, _CREATE_VERBS), doc_anchor="be-clear-and-direct")


def r_no_output_format(doc: Doc) -> Iterator[Finding]:
    if doc.role == "system":
        return
    if doc.n_words < 6:
        return
    if not re.search(_CREATE_VERBS + r"|\b(summari[sz]e|extract|classif|list|return|output|produce|respond)\b",
                     doc.text, re.I):
        return
    if re.search(_FORMAT_WORDS, doc.text, re.I):
        return
    yield Finding(
        "clarity/no-output-format", "", "No output format specified",
        "You ask Claude to produce something but never say what shape the "
        "output should take.",
        "State the desired output format explicitly (e.g. 'Return a JSON array "
        "of {name, score}', or 'Answer in 2-3 prose paragraphs').",
        line=0, doc_anchor="be-clear-and-direct")


def r_unordered_steps(doc: Doc) -> Iterator[Finding]:
    seq = len(re.findall(_SEQ_WORDS, doc.text, re.I))
    if seq < 2:
        return
    has_list = any(re.match(r"\s*(\d+[.)]|[-*+])\s+", ln) for ln in doc.lines)
    if has_list:
        return
    yield Finding(
        "clarity/unordered-steps", "", "Sequential steps not in a list",
        "The prompt describes multiple ordered steps in prose. Order and "
        "completeness are easier for Claude to honor as a numbered list.",
        "Provide the instructions as a numbered list or bullet points.",
        line=_find_line(doc, _SEQ_WORDS), doc_anchor="be-clear-and-direct")


def r_negative_without_reason(doc: Doc) -> Iterator[Finding]:
    m = _PROHIBITION_RE.search(doc.text)
    if not m:
        return
    if re.search(_REASON_WORDS, doc.text, re.I):
        return
    yield Finding(
        "context/negative-without-reason", "", "Prohibition lacks a reason",
        f"'{m.group(0)}' tells Claude what to avoid but not why. Explaining the "
        "motivation lets Claude generalize the rule correctly.",
        "Add the reason, e.g. instead of 'NEVER use ellipses' say 'Your response "
        "will be read aloud by a text-to-speech engine, so never use ellipses "
        "since it will not know how to pronounce them.'",
        line=doc.line_of(m.start()), doc_anchor="add-context-to-improve-performance")


def r_negative_format(doc: Doc) -> Iterator[Finding]:
    m = re.search(r"\b(do not|don'?t|no|never|avoid)\b[^.\n]{0,40}\b(markdown|bullet|list|heading|emoji|formatting)\b",
                  doc.text, re.I)
    if not m:
        return
    yield Finding(
        "format/negative-instruction", "", "Says what NOT to do for formatting",
        "Negative formatting instructions ('do not use markdown') steer worse "
        "than positive ones.",
        "Tell Claude what to do instead ('Write in smoothly flowing prose "
        "paragraphs') and/or use an XML format indicator "
        "(<smoothly_flowing_prose_paragraphs>...).",
        line=doc.line_of(m.start()), doc_anchor="control-the-format-of-responses")


def r_untagged_example(doc: Doc) -> Iterator[Finding]:
    has_tag = any(t.name in ("example", "examples") for t in doc.tags)
    if has_tag:
        return
    m = re.search(r"(?mi)^\s*(example\s*\d*\s*:|for (example|instance)\b|e\.g\.,?\s+\S)", doc.text)
    if not m:
        return
    yield Finding(
        "examples/untagged-example", "", "Example not wrapped in <example> tags",
        "Examples are one of the most reliable steering tools, but Claude parses "
        "them best when they're clearly delimited.",
        "Wrap each example in <example> tags (multiple in <examples>) so Claude "
        "distinguishes them from instructions.",
        line=doc.line_of(m.start()), doc_anchor="use-examples-effectively")


def r_fewshot_count(doc: Doc, lo: int = 3, hi: int = 5) -> Iterator[Finding]:
    n = sum(1 for t in doc.tags if t.name == "example" and not t.closing)
    if n == 0:
        return
    if lo <= n <= hi:
        return
    if n < lo:
        msg = f"Only {n} example(s) provided."
    else:
        msg = f"{n} examples provided - more than needed risks Claude latching onto incidental patterns."
    yield Finding(
        "examples/few-shot-count", "", "Few-shot example count outside 3-5",
        msg + " The doc recommends 3-5 relevant, diverse examples.",
        f"Aim for {lo}-{hi} examples that are relevant (mirror the real case) and "
        "diverse (cover edge cases).",
        line=0, doc_anchor="use-examples-effectively")


def r_xml_unbalanced(doc: Doc) -> Iterator[Finding]:
    counts: dict[str, list[int]] = {}
    for t in doc.tags:
        if t.selfclose:
            continue
        counts.setdefault(t.name, [0, 0])
        if t.closing:
            counts[t.name][1] += 1
        else:
            counts[t.name][0] += 1
    for name, (opens, closes) in counts.items():
        if opens == closes:
            continue
        first = next((t for t in doc.tags if t.name == name and not t.selfclose), None)
        kind = "unclosed" if opens > closes else "stray closing"
        yield Finding(
            "xml/unbalanced-tags", "", "Unbalanced XML tag",
            f"<{name}> appears {opens} open / {closes} close - {kind}. Malformed "
            "structure makes Claude misparse where content begins and ends.",
            f"Balance the <{name}> ... </{name}> tags (or use a self-closing form "
            "if it's a placeholder).",
            line=first.line if first else 0, doc_anchor="structure-prompts-with-xml-tags")


def r_xml_missing_structure(doc: Doc) -> Iterator[Finding]:
    if doc.n_words < 120:
        return
    if doc.tags:
        return
    has_instruction = re.search(_CREATE_VERBS + r"|\b(analy[sz]e|summari[sz]e|classif|extract|answer|review)\b",
                                doc.text, re.I)
    blocky = doc.text.count("\n\n") >= 2 or re.search(r"(?m)^(---|===|\#{1,3}\s)", doc.text)
    if not (has_instruction and blocky):
        return
    yield Finding(
        "xml/missing-structure", "", "Mixed content with no XML structure",
        "This is a long prompt mixing instructions with context/data but uses no "
        "XML tags, so the boundaries are ambiguous.",
        "Wrap each content type in its own descriptive tag, e.g. <instructions>, "
        "<context>, <input>, <examples>.",
        line=0, doc_anchor="structure-prompts-with-xml-tags")


def r_xml_inconsistent(doc: Doc) -> Iterator[Finding]:
    names = {t.name for t in doc.tags if not t.selfclose}
    if len(names) < 2:
        return
    styles = set()
    for n in names:
        if "-" in n:
            styles.add("kebab")
        elif "_" in n:
            styles.add("snake")
        elif re.search(r"[a-z][A-Z]", n):
            styles.add("camel")
        else:
            styles.add("flat")
    styles.discard("flat")
    if len(styles) <= 1:
        return
    yield Finding(
        "xml/inconsistent-tag-style", "", "Inconsistent XML tag naming",
        f"Tag names mix conventions ({', '.join(sorted(styles))}). Consistency "
        "helps Claude (and you) reason about structure.",
        "Pick one convention (snake_case is common) and use consistent, "
        "descriptive names across the prompt.",
        line=0, doc_anchor="structure-prompts-with-xml-tags")


def r_no_role(doc: Doc) -> Iterator[Finding]:
    if doc.role != "system":
        return
    if re.search(r"\byou are\b|\bact as\b|\byour role\b|\bas an? \w+ (assistant|expert|engineer)\b",
                 doc.text, re.I):
        return
    yield Finding(
        "role/no-role", "", "System prompt sets no role",
        "Setting a role in the system prompt focuses Claude's behavior and tone. "
        "Even a single sentence helps.",
        "Open with a role, e.g. 'You are a helpful coding assistant specializing "
        "in Python.'",
        line=0, doc_anchor="give-claude-a-role")


def r_longctx_query_position(doc: Doc, threshold: int = 20000) -> Iterator[Finding]:
    if doc.est_tokens < threshold:
        return
    tail = doc.text[int(doc.n_chars * 0.80):]
    query_in_tail = bool(re.search(r"\?|\b(analy[sz]e|summari[sz]e|identify|list|find|recommend|answer|explain|extract)\b",
                                   tail, re.I))
    if query_in_tail:
        return
    yield Finding(
        "longctx/query-not-at-end", "", "Query not at the end of a long prompt",
        f"This prompt is ~{doc.est_tokens:,} tokens but the instruction/query "
        "doesn't appear near the end. For 20k+ token inputs, putting the query "
        "last can improve quality by up to 30%.",
        "Place long documents/data at the TOP and move your query, instructions, "
        "and examples to the END.",
        line=0, doc_anchor="long-context-prompting")


def r_longctx_doc_tags(doc: Doc, threshold: int = 20000) -> Iterator[Finding]:
    if doc.est_tokens < threshold:
        return
    if any(t.name in ("document", "documents", "document_content") for t in doc.tags):
        return
    yield Finding(
        "longctx/no-document-tags", "", "Long multi-doc input lacks <document> tags",
        "Large inputs are easier for Claude to navigate when each source is "
        "wrapped with metadata.",
        "Wrap each document in <document index=\"n\"> with <source> and "
        "<document_content> subtags, all inside <documents>.",
        line=0, doc_anchor="long-context-prompting")


def r_longctx_quote_grounding(doc: Doc, threshold: int = 20000) -> Iterator[Finding]:
    if doc.est_tokens < threshold:
        return
    if re.search(r"\bquote", doc.lower):
        return
    yield Finding(
        "longctx/no-quote-grounding", "", "Long-doc task without quote grounding",
        "For long-document tasks, asking Claude to first pull relevant quotes "
        "helps it cut through the noise.",
        "Ask Claude to extract relevant quotes into <quotes> tags first, then "
        "perform the task based on those quotes.",
        line=0, doc_anchor="long-context-prompting")


def r_suggest_not_act(doc: Doc) -> Iterator[Finding]:
    m = re.search(r"\b(can|could|would) you (please )?(suggest|recommend|propose)\b", doc.text, re.I)
    if not m:
        return
    if not re.search(r"\b(code|function|file|bug|test|refactor|implement|change|fix|edit)\b", doc.text, re.I):
        return
    yield Finding(
        "action/suggest-not-act", "", "Ambiguous 'suggest' may not trigger action",
        "Phrasing like 'can you suggest...' often makes Claude only describe "
        "changes instead of making them.",
        "If you want action, use an explicit imperative: 'Change this function to "
        "improve its performance' or 'Make these edits to the authentication flow.'",
        line=doc.line_of(m.start()), doc_anchor="tool-usage")


def r_overtrigger_emphasis(doc: Doc, max_caps: int = 3) -> Iterator[Finding]:
    caps = re.findall(r"\b(CRITICAL|MUST|ALWAYS|NEVER|IMPORTANT|MANDATORY|REQUIRED)\b", doc.text)
    bangs = doc.text.count("!!!")
    if len(caps) + bangs < max_caps:
        return
    yield Finding(
        "emphasis/overtrigger-language", "", "Aggressive emphasis may overtrigger",
        f"Found {len(caps)} all-caps directives" + (f" and {bangs} '!!!'" if bangs else "") +
        ". Current models follow instructions precisely; shouty language that was "
        "needed for older models now causes overtriggering.",
        "Dial it back to normal phrasing - 'Use this tool when...' instead of "
        "'CRITICAL: You MUST use this tool when...'.",
        line=0, doc_anchor="tool-usage")


def r_prefill(doc: Doc) -> Iterator[Finding]:
    if doc.role != "assistant":
        return
    yield Finding(
        "format/prefill-detected", "", "Assistant prefill is unsupported on 4.6+",
        "Prefilled responses on the last assistant turn return a 400 error on "
        "Claude 4.6+ models.",
        "Remove the prefill. Use Structured Outputs / tool calling for format "
        "control, or move continuations into the user turn.",
        line=0, doc_anchor="migrating-away-from-prefilled-responses")


def r_preamble_prefill_text(doc: Doc) -> Iterator[Finding]:
    if doc.role != "assistant":
        return
    m = re.match(r"\s*(here (is|are|'s)|based on|sure[,!]|certainly[,!]|i'?ll )", doc.text, re.I)
    if not m:
        return
    yield Finding(
        "format/preamble-prefill", "", "Looks like a preamble-stripping prefill",
        "This assistant text reads like a prefill used to skip a preamble - no "
        "longer supported on 4.6+.",
        "Instead instruct in the system/user turn: 'Respond directly without "
        "preamble. Do not start with phrases like \"Here is...\".'",
        line=1, doc_anchor="migrating-away-from-prefilled-responses")


def r_deprecated_model(doc: Doc) -> Iterator[Finding]:
    m = re.search(r"\b(claude-?(?:instant|1|2|3(?:\.\d)?)|claude-3[.-]\w+|"
                  r"text-davinci|gpt-[0-9]|claude-(?:opus|sonnet|haiku)-3)\b",
                  doc.text, re.I)
    if not m:
        return
    yield Finding(
        "model/deprecated-model-ref", "", "References an old/foreign model id",
        f"'{m.group(0)}' is a deprecated or non-current model string.",
        "Default to a current Claude model, e.g. claude-opus-4-8 (or "
        "claude-sonnet-4-6 / claude-haiku-4-5), unless you specifically need another.",
        line=doc.line_of(m.start()), doc_anchor="model-self-knowledge")


def r_prescriptive_thinking(doc: Doc) -> Iterator[Finding]:
    steps = len(re.findall(r"(?m)^\s*(step \d|stage \d|\d+[.)]\s)", doc.text, re.I))
    if steps < 6:
        return
    yield Finding(
        "thinking/prescriptive-steps", "", "Highly prescriptive step-by-step plan",
        f"{steps} explicit steps. With adaptive thinking, general instructions "
        "('think thoroughly') often beat a hand-written plan.",
        "Prefer general guidance and let Claude reason; reserve rigid steps for "
        "when order genuinely matters.",
        line=0, doc_anchor="leverage-thinking-interleaved-thinking-capabilities")


def r_overengineering_guard(doc: Doc) -> Iterator[Finding]:
    if not re.search(r"\b(implement|refactor|build|add a feature|write (a|the) code)\b", doc.text, re.I):
        return
    if re.search(r"\b(minimal|don'?t over|only .* requested|keep .* simple|no extra)\b", doc.text, re.I):
        return
    yield Finding(
        "agentic/overengineering-guard", "", "Coding task without a scope guard",
        "Agent models tend to over-engineer (extra files, abstractions, "
        "speculative flexibility) unless constrained.",
        "Add a scope guard, e.g. 'Avoid over-engineering. Only make changes that "
        "are directly requested or clearly necessary. Keep solutions simple.'",
        line=0, doc_anchor="overeagerness")


# --- Cursor agent rules ------------------------------------------------------
_CLAUDE_XML_TAGS = frozenset({
    "context", "document", "documents", "document_content", "source",
    "example", "examples", "instructions", "quotes",
})
_FILE_PATH_RE = re.compile(
    r"(?<![@/\w])"
    r"(?:"
    r"(?:[\w.-]+/)+[\w.-]+\.\w{1,8}"          # path/to/file.ext
    r"|\b[\w.-]+\.(?:tsx?|jsx?|py|rs|go|java|cs|cpp|c|h|md|json|ya?ml|toml|sql|sh|ps1)\b"
    r")",
    re.I,
)


def r_cursor_claude_xml(doc: Doc) -> Iterator[Finding]:
    hits = [t for t in doc.tags if t.name in _CLAUDE_XML_TAGS and not t.closing]
    if not hits:
        return
    first = hits[0]
    yield Finding(
        "cursor/claude-xml-tags", "", "Claude-style XML tags in a Cursor prompt",
        f"Found <{first.name}> — Cursor Agent uses @ mentions, Rules, and "
        "AGENTS.md for context, not Claude XML scaffolding.",
        "Replace XML blocks with @file/@folder mentions for code context, and "
        "move standing instructions into .cursor/rules or AGENTS.md.",
        line=first.line, doc_anchor="prompting", doc_url=CURSOR_DOC_URL)


def r_cursor_file_without_at(doc: Doc) -> Iterator[Finding]:
    if "@" in doc.text:
        return
    m = _FILE_PATH_RE.search(doc.code_stripped)
    if not m:
        return
    if not re.search(r"\b(in|read|edit|fix|update|change|review|check|open|modify|refactor)\b",
                     doc.text, re.I):
        return
    yield Finding(
        "cursor/file-without-at", "", "File path mentioned without @ mention",
        f"'{m.group(0)}' looks like a file reference but isn't attached with @.",
        "Type @ in chat and pick the file or folder (e.g. @src/app.ts) so Agent "
        "gets the right context. Skip @ when you're unsure — Agent can search.",
        line=doc.line_of(m.start()), doc_anchor="prompting", doc_url=CURSOR_DOC_URL)


def r_cursor_rules_in_prompt(doc: Doc) -> Iterator[Finding]:
    if doc.n_words < 80:
        return
    policy_lines = sum(
        1 for ln in doc.lines
        if re.match(r"\s*[-*+]\s+(Always|Never|Must|Use |Prefer |Don'?t |Do not )",
                    ln, re.I)
    )
    if policy_lines < 6:
        return
    if re.search(r"\.cursor/rules|AGENTS\.md|user rules", doc.text, re.I):
        return
    yield Finding(
        "cursor/rules-in-prompt", "", "Standing policies pasted into the prompt",
        f"{policy_lines} policy-style bullet lines detected. Cursor Rules persist "
        "across chats; repeating them in every prompt wastes context.",
        "Move recurring standards to .cursor/rules, AGENTS.md, or Cursor Settings "
        "→ Rules. Reference a canonical example file with @ instead of copying code.",
        line=0, doc_anchor="rules", doc_url="https://cursor.com/docs/rules")


def r_cursor_plan_without_boundary(doc: Doc) -> Iterator[Finding]:
    if doc.n_words < 50:
        return
    if not re.search(r"\b(implement|refactor|build|add|migrate|rewrite|architect)\b", doc.text, re.I):
        return
    if re.search(r"\b(plan only|do not write|don't write|no code|minimal|only .* requested|"
                 r"smallest|just fix|single file|one file)\b", doc.text, re.I):
        return
    yield Finding(
        "cursor/plan-without-boundary", "", "Large coding task without scope boundary",
        "Broad implementation/refactor prompts often cause Agent to touch more "
        "than you intended.",
        "Add scope: target files (@path), 'minimal diff', 'only what's needed', "
        "or say 'plan first, do not write code' if you want design before edits.",
        line=0, doc_anchor="using", doc_url="https://cursor.com/docs/cli/using")


# --- registry ----------------------------------------------------------------
def _build_registry(thresholds: dict) -> dict[str, Rule]:
    lc = thresholds.get("long_doc_tokens", 20000)
    lo = thresholds.get("examples_min", 3)
    hi = thresholds.get("examples_max", 5)
    caps = thresholds.get("emphasis_max", 3)

    rules = [
        Rule("clarity/vague-task", "warn", "Vague task with no specifics",
             "Short creation prompts with no format/constraints. Be specific and "
             "request above-and-beyond work.", "be-clear-and-direct", r_vague_task),
        Rule("clarity/no-output-format", "info", "No output format specified",
             "Asking to produce output without stating its shape.", "be-clear-and-direct",
             r_no_output_format),
        Rule("clarity/unordered-steps", "info", "Sequential steps not in a list",
             "Ordered steps in prose; use a numbered list when order/completeness matters.",
             "be-clear-and-direct", r_unordered_steps),
        Rule("context/negative-without-reason", "warn", "Prohibition lacks a reason",
             "Telling Claude what to avoid without why; add motivation so it generalizes.",
             "add-context-to-improve-performance", r_negative_without_reason),
        Rule("format/negative-instruction", "warn", "Says what NOT to do for formatting",
             "Negative format instructions steer worse than positive ones + XML indicators.",
             "control-the-format-of-responses", r_negative_format),
        Rule("examples/untagged-example", "warn", "Example not wrapped in <example> tags",
             "Examples present but not delimited; wrap in <example>/<examples>.",
             "use-examples-effectively", r_untagged_example),
        Rule("examples/few-shot-count", "info", "Few-shot example count outside 3-5",
             "Doc recommends 3-5 relevant, diverse examples.", "use-examples-effectively",
             lambda d: r_fewshot_count(d, lo, hi)),
        Rule("xml/unbalanced-tags", "error", "Unbalanced XML tag",
             "An XML tag is opened but not closed (or vice versa). Structural error.",
             "structure-prompts-with-xml-tags", r_xml_unbalanced),
        Rule("xml/missing-structure", "warn", "Mixed content with no XML structure",
             "Long prompt mixing instructions+context+data with no tags.",
             "structure-prompts-with-xml-tags", r_xml_missing_structure),
        Rule("xml/inconsistent-tag-style", "info", "Inconsistent XML tag naming",
             "Tag names mix snake/kebab/camel conventions.", "structure-prompts-with-xml-tags",
             r_xml_inconsistent),
        Rule("role/no-role", "info", "System prompt sets no role",
             "System prompts should set a role to focus behavior/tone.", "give-claude-a-role",
             r_no_role),
        Rule("longctx/query-not-at-end", "warn", "Query not at the end of a long prompt",
             "For 20k+ token inputs, put the query last (up to 30% better).",
             "long-context-prompting", lambda d: r_longctx_query_position(d, lc)),
        Rule("longctx/no-document-tags", "warn", "Long multi-doc input lacks <document> tags",
             "Wrap each source in <document>/<source>/<document_content>.",
             "long-context-prompting", lambda d: r_longctx_doc_tags(d, lc)),
        Rule("longctx/no-quote-grounding", "info", "Long-doc task without quote grounding",
             "Ask Claude to extract relevant quotes first for long docs.",
             "long-context-prompting", lambda d: r_longctx_quote_grounding(d, lc)),
        Rule("action/suggest-not-act", "warn", "Ambiguous 'suggest' may not trigger action",
             "'Can you suggest...' often yields suggestions, not edits; use imperatives.",
             "tool-usage", r_suggest_not_act),
        Rule("emphasis/overtrigger-language", "warn", "Aggressive emphasis may overtrigger",
             "Shouty all-caps directives overtrigger current models; dial back.",
             "tool-usage", lambda d: r_overtrigger_emphasis(d, caps)),
        Rule("format/prefill-detected", "error", "Assistant prefill is unsupported on 4.6+",
             "Last-turn assistant prefill returns 400 on 4.6+.",
             "migrating-away-from-prefilled-responses", r_prefill),
        Rule("format/preamble-prefill", "warn", "Looks like a preamble-stripping prefill",
             "Assistant text that reads like a preamble-skipping prefill.",
             "migrating-away-from-prefilled-responses", r_preamble_prefill_text),
        Rule("model/deprecated-model-ref", "warn", "References an old/foreign model id",
             "Mentions a deprecated/non-current model string.", "model-self-knowledge",
             r_deprecated_model),
        # opinionated, default OFF
        Rule("thinking/prescriptive-steps", "off", "Highly prescriptive step-by-step plan",
             "Many hard-coded steps; general guidance often reasons better.",
             "leverage-thinking-interleaved-thinking-capabilities", r_prescriptive_thinking),
        Rule("agentic/overengineering-guard", "off", "Coding task without a scope guard",
             "Suggest adding an anti-over-engineering guard to coding prompts.",
             "overeagerness", r_overengineering_guard),
        # Cursor agent (default off; cursor preset enables)
        Rule("cursor/claude-xml-tags", "off", "Claude-style XML tags in a Cursor prompt",
             "Cursor uses @ mentions and Rules, not Claude XML scaffolding.",
             "prompting", r_cursor_claude_xml),
        Rule("cursor/file-without-at", "off", "File path mentioned without @ mention",
             "Attach known files with @ instead of bare path strings.",
             "prompting", r_cursor_file_without_at),
        Rule("cursor/rules-in-prompt", "off", "Standing policies pasted into the prompt",
             "Recurring standards belong in .cursor/rules or AGENTS.md.",
             "rules", r_cursor_rules_in_prompt),
        Rule("cursor/plan-without-boundary", "off", "Large coding task without scope boundary",
             "Broad agent tasks need file targets or explicit scope limits.",
             "using", r_cursor_plan_without_boundary),
    ]
    return {r.id: r for r in rules}


# =============================================================================
# CONFIG
# =============================================================================
DEFAULT_CONFIG = {
    "profile": "claude",
    "extends": "anthropic-best-practices",
    "doc_url": DOC_URL,
    "fail_on": "error",
    "thresholds": {
        "long_doc_tokens": 20000,
        "examples_min": 3,
        "examples_max": 5,
        "emphasis_max": 3,
    },
    "rules": {},  # rule_id -> "off"|"info"|"warn"|"error" overrides
}


def apply_preset(cfg: dict, profile: str) -> None:
    preset = PRESETS.get(profile)
    if not preset:
        return
    cfg["profile"] = profile
    cfg["doc_url"] = preset.get("doc_url", DOC_URL)
    if "fail_on" in preset:
        cfg["fail_on"] = preset["fail_on"]
    cfg["thresholds"].update(preset.get("thresholds", {}))
    for rid, sev in preset.get("rules", {}).items():
        cfg["rules"][rid] = sev


def load_config(explicit: str | None, profile: str | None = None) -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
    env_profile = os.environ.get("PROMPTLINT_PROFILE")
    chosen = profile or env_profile

    user: dict = {}
    paths: list[str] = []
    if explicit:
        paths = [explicit]
    else:
        paths = [
            os.path.join(os.getcwd(), ".promptlintrc.json"),
            os.path.expanduser("~/.config/promptlint/config.json"),
        ]
    for p in paths:
        if p and os.path.isfile(p):
            try:
                user = json.loads(open(p, encoding="utf-8").read())
            except Exception as e:
                sys.stderr.write(f"prompt-lint: bad config {p}: {e}\n")
                user = {}
                continue
            cfg["_source"] = p
            break

    chosen = chosen or user.get("profile") or user.get("extends")
    chosen = PROFILE_ALIASES.get(chosen, chosen) if chosen else None
    if chosen in PRESETS:
        apply_preset(cfg, chosen)
    elif chosen:
        sys.stderr.write(f"prompt-lint: unknown profile '{chosen}', using claude defaults\n")

    if user:
        if "profile" in user and user["profile"] in PRESETS:
            apply_preset(cfg, user["profile"])
        elif "profile" in user and user["profile"] in PROFILE_ALIASES:
            apply_preset(cfg, PROFILE_ALIASES[user["profile"]])
        if "fail_on" in user:
            cfg["fail_on"] = user["fail_on"]
        cfg["thresholds"].update(user.get("thresholds", {}))
        cfg["rules"].update(user.get("rules", {}))
    return cfg


# =============================================================================
# SUPPRESSION DIRECTIVES
# =============================================================================
def parse_suppressions(text: str):
    """Return (disable_file, disabled_all, disabled_rules, line_disables)."""
    disable_file = bool(re.search(r"promptlint-disable-file\b", text))
    disabled_all = False
    disabled: set[str] = set()
    line_dis: dict[int, set] = {}
    for i, ln in enumerate(text.splitlines(), 1):
        m = re.search(r"promptlint-disable-line\s+([\w/,\s-]+)", ln)
        if m:
            line_dis.setdefault(i, set()).update(_split_ids(m.group(1)))
        m = re.search(r"promptlint-disable(?!-line|-file)\s*([\w/,\s-]*)", ln)
        if m:
            ids = _split_ids(m.group(1))
            if ids:
                disabled.update(ids)
            else:
                disabled_all = True
    return disable_file, disabled_all, disabled, line_dis


def _split_ids(s: str) -> set:
    return {p.strip() for p in re.split(r"[,\s]+", s) if p.strip() and "/" in p}


# =============================================================================
# ENGINE
# =============================================================================
def lint(text: str, role: str, config: dict,
         select: set | None = None, ignore: set | None = None) -> list[Finding]:
    registry = _build_registry(config["thresholds"])
    overrides = dict(config.get("rules", {}))
    df, dall, drules, line_dis = parse_suppressions(text)
    if df:
        return []
    doc = Doc(text, role=role)
    findings: list[Finding] = []
    for rid, rule in registry.items():
        sev = overrides.get(rid, rule.default)
        if select and rid not in select:
            sev = "off"
        if ignore and rid in ignore:
            sev = "off"
        if sev == "off":
            continue
        if dall or rid in drules:
            continue
        try:
            for f in rule.check(doc):
                if f.line and rid in line_dis.get(f.line, set()):
                    continue
                f.severity = sev
                f.title = f.title or rule.title
                f.doc_anchor = f.doc_anchor or rule.doc_anchor
                if not f.doc_url:
                    if rid.startswith("cursor/"):
                        f.doc_url = config.get("doc_url", CURSOR_DOC_URL)
                    else:
                        f.doc_url = config.get("doc_url", DOC_URL)
                findings.append(f)
        except Exception as e:  # a rule must never crash the gate
            sys.stderr.write(f"prompt-lint: rule {rid} errored: {e}\n")
    findings.sort(key=lambda f: (-SEV_RANK[f.severity], f.line, f.rule_id))
    return findings


def counts(findings: list[Finding]) -> dict:
    c = {"error": 0, "warn": 0, "info": 0}
    for f in findings:
        c[f.severity] = c.get(f.severity, 0) + 1
    return c


# =============================================================================
# OUTPUT
# =============================================================================
class C:
    def __init__(self, on: bool):
        self.on = on

    def __call__(self, s, code):
        return f"\033[{code}m{s}\033[0m" if self.on else s


SEV_COLOR = {"error": "1;31", "warn": "1;33", "info": "1;36"}
SEV_ICON = {"error": "x", "warn": "!", "info": "i"}


def render_human(findings: list[Finding], cfg: dict, color: bool, src: str) -> str:
    c = C(color)
    out = []
    if not findings:
        return c("OK prompt-lint: clean - no findings.", "1;32")
    for f in findings:
        loc = f"{src}:{f.line}" if f.line else src
        head = (f"{c(SEV_ICON.get(f.severity,'*'), SEV_COLOR.get(f.severity,'0'))} "
                f"{c(f.severity.upper(), SEV_COLOR.get(f.severity,'0'))} "
                f"{c(f.rule_id, '0;90')}  {c(loc,'0;90')}")
        out.append(head)
        out.append(f"    {f.title}")
        out.append(f"    {f.message}")
        out.append(c(f"    fix: {f.fix}", "0;32"))
        out.append(c(f"    doc: {f.doc_link()}", "0;90"))
        out.append("")
    cc = counts(findings)
    out.append(c(f"{cc['error']} error, {cc['warn']} warn, {cc['info']} info "
                 f"(fail-on: {cfg['fail_on']})", "1"))
    return "\n".join(out)


def to_json(findings: list[Finding], cfg: dict, ok: bool) -> str:
    return json.dumps({
        "ok": ok,
        "profile": cfg.get("profile", "claude"),
        "fail_on": cfg["fail_on"],
        "counts": counts(findings),
        "findings": [asdict(f) | {"doc": f.doc_link()} for f in findings],
    }, indent=2)


def gate_failed(findings: list[Finding], fail_on: str) -> bool:
    if fail_on == "off":
        return False
    return any(sev_ge(f.severity, fail_on) for f in findings)


# =============================================================================
# CLI
# =============================================================================
def read_input(args) -> str:
    if args.content is not None:
        return args.content.lstrip("﻿")
    if args.file and args.file != "-":
        return open(args.file, encoding="utf-8-sig").read()
    if not sys.stdin.isatty():
        raw = sys.stdin.buffer.read()
        return raw.decode("utf-8-sig", errors="replace")
    return ""


def cmd_list_rules(color: bool, profile: str | None = None):
    cfg = load_config(None, profile)
    reg = _build_registry(cfg["thresholds"])
    c = C(color)
    prof = cfg.get("profile", "claude")
    print(f"profile: {prof}  (doc: {cfg.get('doc_url', DOC_URL)})")
    for rid, r in reg.items():
        sev = cfg["rules"].get(rid, r.default)
        if sev == "off":
            continue
        print(f"{c(rid,'1'):42}  {c(sev, SEV_COLOR.get(sev,'0;90'))}\t{r.title}")


def cmd_list_profiles(color: bool):
    c = C(color)
    for name, preset in PRESETS.items():
        n_on = sum(1 for s in preset.get("rules", {}).values() if s != "off")
        print(f"{c(name,'1'):10}  {preset.get('doc_url', DOC_URL)}  ({n_on} rule overrides)")


def rule_doc_url(rule_id: str) -> str:
    if rule_id.startswith("cursor/"):
        return CURSOR_DOC_URL if rule_id in ("cursor/claude-xml-tags", "cursor/file-without-at") else "https://cursor.com/docs/rules"
    return DOC_URL


def cmd_explain(rule_id: str, color: bool, profile: str | None = None) -> int:
    reg = _build_registry(DEFAULT_CONFIG["thresholds"])
    r = reg.get(rule_id)
    if not r:
        sys.stderr.write(f"prompt-lint: unknown rule '{rule_id}'\n")
        return 2
    cfg = load_config(None, profile)
    sev = cfg["rules"].get(rule_id, r.default)
    c = C(color)
    doc = rule_doc_url(rule_id)
    print(c(r.id, "1"))
    print(f"  title:    {r.title}")
    print(f"  profile:  {cfg.get('profile', 'claude')} (effective severity: {sev})")
    print(f"  default:  {r.default}")
    print(f"  why:      {r.rationale}")
    print(f"  doc:      {doc}#{r.doc_anchor}" if r.doc_anchor else f"  doc:      {doc}")
    print(f"  disable:  add 'promptlint-disable {r.id}' in the prompt, "
          f"or set \"{r.id}\": \"off\" in .promptlintrc.json")
    return 0


def watch(args, cfg, select, ignore, color):
    path = args.file
    if not path or path == "-":
        sys.stderr.write("prompt-lint: --watch requires a FILE\n")
        return 2
    sys.stderr.write(f"prompt-lint: watching {path} (Ctrl-C to stop)\n")
    last = None
    try:
        while True:
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                mtime = None
            if mtime != last:
                last = mtime
                try:
                    text = open(path, encoding="utf-8").read()
                except OSError:
                    time.sleep(0.4)
                    continue
                findings = lint(text, args.role, cfg, select, ignore)
                sys.stdout.write("\033[2J\033[H" if color else "\n")
                ts = time.strftime("%H:%M:%S")
                sys.stdout.write(f"prompt-lint --watch {path}  [{ts}]\n\n")
                sys.stdout.write(render_human(findings, cfg, color, path) + "\n")
                sys.stdout.flush()
            time.sleep(0.4)
    except KeyboardInterrupt:
        sys.stderr.write("\nprompt-lint: stopped.\n")
        return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="prompt-lint",
        description="Deterministic, zero-token linter for agent prompts. "
                    "Profiles: claude (Anthropic best practices), cursor (Cursor Agent).")
    ap.add_argument("file", nargs="?", help="prompt file (or '-'/stdin)")
    ap.add_argument("-c", "--content", help="lint literal text")
    ap.add_argument("--format", choices=("human", "json"), default="human")
    ap.add_argument("--config", help="path to .promptlintrc.json")
    ap.add_argument("--profile", choices=tuple(PRESETS.keys()),
                    help="rule preset: claude (default) or cursor")
    ap.add_argument("--role", choices=("user", "system", "assistant"), default="user")
    ap.add_argument("--fail-on", choices=SEVERITIES, dest="fail_on", help="override gate threshold")
    ap.add_argument("--select", help="only these rule ids (comma-sep)")
    ap.add_argument("--ignore", help="disable these rule ids (comma-sep)")
    ap.add_argument("--watch", action="store_true", help="live re-lint on file change")
    ap.add_argument("--list-rules", action="store_true")
    ap.add_argument("--list-profiles", action="store_true")
    ap.add_argument("--explain", metavar="RULE_ID")
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args(argv)

    color = (not args.no_color) and sys.stdout.isatty() and not os.environ.get("NO_COLOR")

    if args.list_rules:
        cmd_list_rules(color, args.profile)
        return 0
    if args.list_profiles:
        cmd_list_profiles(color)
        return 0
    if args.explain:
        return cmd_explain(args.explain, color, args.profile)

    cfg = load_config(args.config, args.profile)
    if args.fail_on:
        cfg["fail_on"] = args.fail_on
    select = {s.strip() for s in args.select.split(",")} if args.select else None
    ignore = {s.strip() for s in args.ignore.split(",")} if args.ignore else None

    if args.watch:
        return watch(args, cfg, select, ignore, color)

    text = read_input(args)
    if not text.strip():
        sys.stderr.write("prompt-lint: no input (give a FILE, stdin, or -c TEXT)\n")
        return 2

    src = args.file if (args.file and args.file != "-") else "<prompt>"
    findings = lint(text, args.role, cfg, select, ignore)
    failed = gate_failed(findings, cfg["fail_on"])

    if args.format == "json":
        print(to_json(findings, cfg, ok=not failed))
    else:
        print(render_human(findings, cfg, color, src))

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
