---
name: chronicle
description: Use this when closing out a substantive Claude Code session — a slice shipped, a long debugging arc, a release cut, or end of day — and you want a structured, actionable retrospective. Generates a Chronicle-style post-mortem (what shipped, what bit us with severity ratings + fixes, recommendations, carry-forward, process rules) to a per-day markdown file and extracts findings into the rote + design-patterns catalogs. Run unprompted at the end of substantive sessions; skip only for trivial conversational turns or pure read-only questions.
---

# Chronicle — Session Post-Mortem Skill

This skill turns a complex Claude Code session into a single actionable retrospective document. Not a commit log, not a standup, not a release note — a **post-mortem with teeth**: what landed, what broke, why, what the user should DO about it.

## When to invoke

- After a session that shipped a meaningful slice (feature, fix, infra change)
- After a long debugging arc that hit multiple surprises
- When the user asks for "chronicle", "post-mortem", "session analysis", "session-review", "what should I do next"
- When closing out for the day and want a record future-you can scan in 60 seconds

Do NOT invoke for trivial conversational turns or pure read-only questions — there's nothing to chronicle.

## What to produce

A single markdown file at:

```
<repo-root>/docs/session-analyses/YYYY-MM-DD-<short-slug>.md
```

If the user is operating across multiple repos, create the file in the repo that owns the **primary** work product of the session. Slug should be 3-6 words capturing the day's headline (e.g. `cert-chain-consumption-and-signup-fix`).

The file MUST have these five sections in this order. Don't reshuffle them — the structure IS the contract; reordering breaks future-you's scanning pattern.

### 1. What Shipped

Every concrete deliverable. Include for each:
- **File paths** (relative to repo root)
- **One-line shape description** — what's in it, not what it's called
- **Commit SHA range** at the top of the section so a reader can `git log` to it
- **Verification evidence** when applicable — openssl output, build success, log lines, etc.

Use a table when there are >3 deliverables; bullets when <3. Don't paste full diffs — link to the files and let the reader open them.

### 2. What Bit Us (and Why)

THE most important section. For each issue encountered during the session, write:

- **Severity** rated `CRITICAL | HIGH | MEDIUM | LOW | COSMETIC` (see rubric below)
- **Root cause** — actual cause, not symptom. Stack trace + identified line, library version, broken assumption, etc.
- **Why it slipped past prior checks** — if applicable. This is where you teach future-you the lesson.
- **Remedy shipped** — what fixed it this session. Reference commits.
- **Recommended follow-up action** — a checkbox list (`- [ ] ...`) of concrete next steps. Each item should be actionable in <2 hours by someone who knows the codebase. NOT "consider refactoring X." YES "add an xUnit test in tests/Y/Z.cs that exercises the codepath."

Severity rubric:
- **CRITICAL** — production user-facing impact RIGHT NOW (paying users blocked, money flowing wrong, security/PII exposure)
- **HIGH** — user-facing impact present but not blocking, OR architectural debt that will become critical within weeks
- **MEDIUM** — internal-only impact, OR latent bug masked by current happy path
- **LOW** — operational hygiene, log noise, single-engineer time-cost
- **COSMETIC** — true cosmetics with no functional cost

Include findings even if they're already fixed. The lesson outlives the fix.

### 3. Recommendations With Wider Reach

Cross-cutting recommendations that aren't tied to a single bug. Examples:
- Patterns worth promoting (e.g. "the discriminator approach we used in X works for Y too")
- Library / dependency exit-ramp candidates (e.g. "PowCap is single-maintainer; consider Turnstile fallback")
- Process / discipline improvements (e.g. "write memory entries immediately after a non-obvious pitfall")

Keep this section short (2-4 items max). It's where structural insights go, not laundry lists.

### 4. Still Bleeding (Carry Forward)

A table of known issues noticed during the session but NOT fixed. Columns: Issue | Severity | Recommended owner / next step. This is the "future-you / future-other-engineer" handoff.

Distinct from §2 because these were not bit-us-today problems — they're the periphery you observed while doing the real work and don't want to forget.

### 5. Session-Scoped Process Recommendations

Process-level rules-of-thumb that came out of this session and should govern future sessions. Reference any memory entries you saved during the session ([[memory-name]] links).

These are the kind of things that would go into a CLAUDE.md or AGENTS.md if they were universally applicable; they're here because they're situational but worth remembering.

## Style rules (binding)

- **Action over description.** Every finding ends with a checkbox or a recommendation. Pure "this happened" without "do this about it" is a journal entry, not a chronicle.
- **Severity ratings are non-negotiable.** Every §2 finding gets one. Don't soften severity to make the day look better.
- **Be specific.** "Add a test" is useless; "Add an xUnit test in tests/Acme.Application.Tests/KeyStoreIntermediateCaSignerTests.cs that exercises SignLeafCertAsync with an RSA-2048 CSR against an ECDsa P-384 intermediate" is useful.
- **Link to commits.** Each major deliverable gets at least one SHA. Each remedy gets the SHA that landed it.
- **No false positives.** If you can't verify something worked, say so. The doc is worthless if future-you can't trust it.
- **Honest about what you didn't do.** If a known issue stayed unfixed, put it in §4 with severity. Don't omit because it makes the day look incomplete.

## Reference example

The first chronicle written with this skill lives at
`example-app/docs/session-analyses/2026-06-02-cert-chain-consumption-and-signup-fix.md`.
Read it before writing a new one — the cadence + density + section weights are calibrated there.

## Execution

1. Survey the session in your head — what shipped (commits), what broke (stack traces / failed probes / user pain), what you noticed but didn't fix, what you'd tell future-you about how to work this codebase.
2. Pick the slug. 3-6 words, kebab-case, captures the headline. If there were two equally-important arcs, mention both in the slug.
3. Write the file. Don't pre-announce sections in chat; write the markdown directly via Write tool.
4. **Extract catalog entries from the session — record EVERY §2/§3/§5 surface into the right catalog so future sessions semantic-search them ([[rote]] / [[design-patterns]]):**

   | Finding type | Catalog | Command |
   |---|---|---|
   | §2 CRITICAL / HIGH bug we hit | anti-patterns | `rote ap add <slug> "<title>" "<symptom>" "<remedy>" --cost "<token impact>"` |
   | §3 architectural insight / pattern applied | design-patterns | drop a markdown file under `design-patterns/<category>/<slug>.md` OR `rote dp use <existing-slug>` if it's a pattern we already have |
   | §3 tool we chose (or explicitly rejected) | technologies | drop `technologies/<category>/<slug>.md` OR `rote tech use <existing-slug>` |
   | §3 reusable code shape that emerged | snippets | drop `snippets/<language>/<slug>.md` with `${PLACEHOLDER}` tokens OR `rote snippet use <slug>` |
   | Tech combination we tried (worked or didn't) | stacks | drop `stacks/<outcome>/<slug>.md` with what_worked / what_didnt / when_to_reuse / when_to_avoid |
   | New shell script you wrote during the session | scripts | already in `/path/to/rote/scripts/` if you followed the rules; `rote script-log` if it ran |

   **Default to recording.** A pattern documented once that bites again is wasted work twice. Cross-link liberally: pattern entries can mention which tech implements them, stack records cite both the patterns and technologies they combined.

5. Commit + push to `main` (or to whichever branch the session's been working on). The commit message should reference what's inside, not just "add chronicle."
6. Report back to the user with the file path + one-line headline + a count of catalog entries created/bumped (e.g. "2 new anti-patterns + 1 new snippet + bumped use_count on Strategy + RabbitMQ").

## Catalog extraction heuristics

Use these prompts on yourself while writing §2/§3/§5:

- **For each remedy I wrote:** is there a pattern slug that names this approach?  If yes, `dp use` it.  If no, write a new design-pattern entry.
- **For each tool I picked:** was the rationale "we use this because X"?  If yes, that's a `tech use`.  If the rationale was "we rejected Y because we need Z" — that's a STACK record under `failure` or a new tech entry's `when_not_to_use` section.
- **For each code block I wrote that has obvious parameters:** that's a snippet.  Replace the parameters with `${PLACEHOLDER}` and drop it under `snippets/<language>/<slug>.md` with a placeholder table.
- **For each "we tried X + Y + Z and it worked / didn't":** that's a stack record.
- **If a session uncovered a new failure mode that has a CONCRETE remedy:** that's an anti-pattern.

## Evolution

This skill is at `~/.claude/skills/chronicle/SKILL.md` — user-scoped, owned by the user. Iterate by editing this file directly. Common changes that may want to land here over time:
- New section types as the kinds of session post-mortems evolve
- Severity rubric refinements (if `CRITICAL` and `HIGH` keep getting confused)
- Style examples for borderline cases
- Default location overrides for non-acme repos

Don't rename the skill — slash-command name `/chronicle` is the user's entry point and renames break that.
