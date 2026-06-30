"""
Rote API — local persistent backend for the Claude
``~/.claude/skills/{chronicle,rote,secret-handling}`` skills.

Listens on 127.0.0.1 only (default port 5572).  Skills hit it via plain
``curl``.

Responsibilities
================

1. **Script discovery.**  ``GET /scripts`` lists every parameterised
   reusable script under ``/path/to/rote/scripts/`` with its
   frontmatter so the LLM grabs an existing tool instead of regenerating
   one.  ``POST /scripts/search`` does semantic similarity search via
   ``sqlite-vec`` over ``purpose + when-to-use`` embeddings.

2. **Secret injection.**  ``POST /vault/inject`` reads named secrets
   from ``secret-vault/secrets.json`` and writes them into a target
   ``.env`` file.  The LLM never sees the bytes — it passes key NAMES
   on the request; the response reports byte counts only.
   ``GET /vault/keys`` lists names + lengths so the LLM can verify a
   secret exists before invoking inject.

3. **Anti-pattern catalog.**  ``POST /anti-patterns`` lets the chronicle
   skill record a newly-discovered token-waste / time-waste pattern
   during a session post-mortem; ``GET /anti-patterns`` lists what's
   known; ``POST /anti-patterns/search`` does semantic search by
   symptom.

Audit: every vault read/inject, anti-pattern write, and search query
lands in ``audit.sqlite`` with key NAMES + byte counts only — never
clear-text secrets.

Backend: SQLite + ``sqlite-vec`` for embeddings, all in one file at
``server/data/audit.sqlite``.  Embeddings are
``all-MiniLM-L6-v2`` (384-dim, CPU-fast).  ``sentence-transformers``
lazy-loaded on first search so cold-start of the server stays cheap.

Run:    ``./start.sh``
Test:   ``curl http://127.0.0.1:5572/healthz``

State is the SQLite file + the on-disk scripts + the vault JSON.
Restart at any time.
"""
from __future__ import annotations

import json
import re
import sqlite3
import struct
import time
import uuid
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Paths.  Everything is relative to the rote root so a fresh
# checkout works without hardcoded ``/home/willi`` paths.
# ---------------------------------------------------------------------------
LIBRARY_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = LIBRARY_ROOT / "scripts"
ANTI_PATTERNS_DIR = LIBRARY_ROOT / "anti-patterns"
DESIGN_PATTERNS_DIR = LIBRARY_ROOT / "design-patterns"
TECHNOLOGIES_DIR = LIBRARY_ROOT / "technologies"
SNIPPETS_DIR = LIBRARY_ROOT / "snippets"
STACKS_DIR = LIBRARY_ROOT / "stacks"
COMMANDS_DIR = LIBRARY_ROOT / "commands"
PROMPTS_DIR = LIBRARY_ROOT / "prompts"
VAULT_PATH = LIBRARY_ROOT / "secret-vault" / "secrets.json"
DB_PATH = Path(__file__).resolve().parent / "data" / "audit.sqlite"

EMBED_DIM = 384  # all-MiniLM-L6-v2
EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

app = FastAPI(
    title="Rote API",
    version="0.2.0",
    description=(
        "Local persistent backend for the Claude rote skills.  "
        "Discover scripts (keyed + semantic), inject vault secrets without "
        "leaking bytes, catalog anti-patterns.  Listens 127.0.0.1 only."
    ),
)

# ---------------------------------------------------------------------------
# DB connection.  We open a fresh sqlite3 connection per request via the
# context manager rather than a long-lived shared one because sqlite3
# connections aren't fully thread-safe under FastAPI's worker model.
# ---------------------------------------------------------------------------


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH))
    c.enable_load_extension(True)
    # Load sqlite-vec.  The package ships a helper that figures out the
    # right loadable path for the current platform.
    import sqlite_vec  # local import so test envs without the dep can still load app.py

    sqlite_vec.load(c)
    c.enable_load_extension(False)
    return c


def _init_schema() -> None:
    """Create tables on first use.  Idempotent."""
    with _conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_unix_ms   INTEGER NOT NULL,
                kind         TEXT    NOT NULL,
                payload_json TEXT    NOT NULL
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS anti_patterns (
                id           TEXT PRIMARY KEY,
                slug         TEXT NOT NULL UNIQUE,
                title        TEXT NOT NULL,
                symptom      TEXT NOT NULL,
                token_cost   TEXT,
                remedy       TEXT NOT NULL,
                first_seen   INTEGER NOT NULL,
                last_seen    INTEGER NOT NULL,
                hit_count    INTEGER NOT NULL DEFAULT 1,
                embed_text   TEXT NOT NULL DEFAULT ''
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS script_index (
                path           TEXT PRIMARY KEY,
                mtime_unix     INTEGER NOT NULL,
                purpose        TEXT NOT NULL DEFAULT '',
                when_to_use    TEXT NOT NULL DEFAULT '',
                touches_secrets TEXT NOT NULL DEFAULT 'unknown',
                frontmatter_json TEXT NOT NULL DEFAULT '{}',
                embed_text     TEXT NOT NULL DEFAULT ''
            )
            """
        )
        # Every script execution lands here.  Indexed by script_name (not
        # path) so renames keep history but the per-script aggregate stays
        # readable.  Mirrors the delegation_log pattern; aggregated into
        # success_rate / avg_duration_ms by the /scripts endpoint.
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS script_run_log (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                script_name   TEXT NOT NULL,
                ts_unix_ms    INTEGER NOT NULL,
                outcome       TEXT NOT NULL CHECK(outcome IN ('success','failure','partial','timeout')),
                exit_code     INTEGER,
                duration_ms   INTEGER,
                caller        TEXT NOT NULL DEFAULT '',
                args_preview  TEXT NOT NULL DEFAULT '',
                notes         TEXT NOT NULL DEFAULT ''
            )
            """
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_script_run_log_name "
            "ON script_run_log(script_name, ts_unix_ms DESC)"
        )
        # Design patterns: the GOOD-patterns counterpart to anti_patterns.
        # When training-data code is mediocre, this catalog is what the LLM
        # consults instead.  Same shape as anti_patterns plus category +
        # structure/example/relationships sections.  use_count tracks which
        # patterns are actively reached for; the rest is reading material.
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS design_patterns (
                id              TEXT PRIMARY KEY,
                slug            TEXT NOT NULL UNIQUE,
                name            TEXT NOT NULL,
                category        TEXT NOT NULL,
                intent          TEXT NOT NULL,
                when_to_use     TEXT NOT NULL DEFAULT '',
                when_not_to_use TEXT NOT NULL DEFAULT '',
                structure       TEXT NOT NULL DEFAULT '',
                example_code    TEXT NOT NULL DEFAULT '',
                relationships   TEXT NOT NULL DEFAULT '',
                references_links TEXT NOT NULL DEFAULT '',
                first_seen      INTEGER NOT NULL,
                last_seen       INTEGER NOT NULL,
                use_count       INTEGER NOT NULL DEFAULT 0,
                embed_text      TEXT NOT NULL DEFAULT ''
            )
            """
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_design_patterns_category "
            "ON design_patterns(category)"
        )
        c.execute(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS design_patterns_vec USING vec0(
                embedding float[{EMBED_DIM}]
            )
            """
        )
        # Technologies — concrete tools that implement the design patterns,
        # with explicit when-to-use vs when-NOT (offline-incompatibility,
        # cloud-lock, scale ceiling, vendor risk).  Use to inform stack
        # decisions: pattern + tech together tell you both "what to build"
        # and "with what."
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS technologies (
                id              TEXT PRIMARY KEY,
                slug            TEXT NOT NULL UNIQUE,
                name            TEXT NOT NULL,
                category        TEXT NOT NULL,
                implements_patterns TEXT NOT NULL DEFAULT '',
                when_to_use     TEXT NOT NULL DEFAULT '',
                when_not_to_use TEXT NOT NULL DEFAULT '',
                limitations     TEXT NOT NULL DEFAULT '',
                cost_notes      TEXT NOT NULL DEFAULT '',
                alternatives    TEXT NOT NULL DEFAULT '',
                tags            TEXT NOT NULL DEFAULT '',
                references_links TEXT NOT NULL DEFAULT '',
                first_seen      INTEGER NOT NULL,
                last_seen       INTEGER NOT NULL,
                use_count       INTEGER NOT NULL DEFAULT 0,
                embed_text      TEXT NOT NULL DEFAULT ''
            )
            """
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_technologies_category "
            "ON technologies(category)"
        )
        c.execute(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS technologies_vec USING vec0(
                embedding float[{EMBED_DIM}]
            )
            """
        )
        # Snippets — parameterized code templates so we stop rewriting the
        # same boilerplate.  body holds the code with ${PLACEHOLDER} tokens;
        # placeholders_json describes each token (name + description +
        # example) so the LLM (or human) knows what to substitute.
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS snippets (
                id              TEXT PRIMARY KEY,
                slug            TEXT NOT NULL UNIQUE,
                name            TEXT NOT NULL,
                language        TEXT NOT NULL,
                applies_patterns TEXT NOT NULL DEFAULT '',
                applies_technologies TEXT NOT NULL DEFAULT '',
                placeholders_json TEXT NOT NULL DEFAULT '[]',
                body            TEXT NOT NULL,
                when_to_use     TEXT NOT NULL DEFAULT '',
                when_not_to_use TEXT NOT NULL DEFAULT '',
                example_expansion TEXT NOT NULL DEFAULT '',
                references_links TEXT NOT NULL DEFAULT '',
                first_seen      INTEGER NOT NULL,
                last_seen       INTEGER NOT NULL,
                use_count       INTEGER NOT NULL DEFAULT 0,
                embed_text      TEXT NOT NULL DEFAULT ''
            )
            """
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_snippets_language "
            "ON snippets(language)"
        )
        c.execute(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS snippets_vec USING vec0(
                embedding float[{EMBED_DIM}]
            )
            """
        )
        # Stacks — witness statements about technology combinations that
        # have been tried.  outcome = success / partial / failure / mixed.
        # Lets future-Claude / future-you check "have we tried this combo
        # before, did it work, what bit us."
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS stacks (
                id              TEXT PRIMARY KEY,
                slug            TEXT NOT NULL UNIQUE,
                name            TEXT NOT NULL,
                technologies    TEXT NOT NULL DEFAULT '',
                patterns        TEXT NOT NULL DEFAULT '',
                context         TEXT NOT NULL DEFAULT '',
                outcome         TEXT NOT NULL CHECK(outcome IN ('success','partial','failure','mixed')),
                what_worked     TEXT NOT NULL DEFAULT '',
                what_didnt      TEXT NOT NULL DEFAULT '',
                when_to_reuse   TEXT NOT NULL DEFAULT '',
                when_to_avoid   TEXT NOT NULL DEFAULT '',
                references_links TEXT NOT NULL DEFAULT '',
                first_seen      INTEGER NOT NULL,
                last_seen       INTEGER NOT NULL,
                use_count       INTEGER NOT NULL DEFAULT 0,
                embed_text      TEXT NOT NULL DEFAULT ''
            )
            """
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_stacks_outcome "
            "ON stacks(outcome)"
        )
        c.execute(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS stacks_vec USING vec0(
                embedding float[{EMBED_DIM}]
            )
            """
        )
        # Commands — the building blocks (apt-get / docker / git / find /
        # rsync / ssh / chmod / systemd / openssl / jq).  Captures the
        # canonical invocation + the GOTCHAS that aren't obvious from the
        # man page + cross-platform equivalents (apt-get / dnf / brew /
        # choco / apk).  Catalog complement to snippets (multi-line code
        # templates) and scripts (parameterized .sh files).
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS commands (
                id              TEXT PRIMARY KEY,
                slug            TEXT NOT NULL UNIQUE,
                name            TEXT NOT NULL,
                family          TEXT NOT NULL,
                command_line    TEXT NOT NULL,
                platform        TEXT NOT NULL DEFAULT '',
                equivalents     TEXT NOT NULL DEFAULT '',
                when_to_use     TEXT NOT NULL DEFAULT '',
                when_not_to_use TEXT NOT NULL DEFAULT '',
                gotchas         TEXT NOT NULL DEFAULT '',
                flags_explained TEXT NOT NULL DEFAULT '',
                examples        TEXT NOT NULL DEFAULT '',
                references_links TEXT NOT NULL DEFAULT '',
                first_seen      INTEGER NOT NULL,
                last_seen       INTEGER NOT NULL,
                use_count       INTEGER NOT NULL DEFAULT 0,
                embed_text      TEXT NOT NULL DEFAULT ''
            )
            """
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_commands_family "
            "ON commands(family)"
        )
        c.execute(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS commands_vec USING vec0(
                embedding float[{EMBED_DIM}]
            )
            """
        )
        # Prompts — reusable, parameterized PROMPTS (natural language, not code):
        # project-init, review/debug, research/design, delivery, and efficiency
        # patterns (looping, goal formats). body holds the prompt with
        # ${PLACEHOLDER} tokens. Indexed from prompts/<category>/<slug>.md.
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS prompts (
                id              TEXT PRIMARY KEY,
                slug            TEXT NOT NULL UNIQUE,
                name            TEXT NOT NULL,
                category        TEXT NOT NULL DEFAULT 'general',
                body            TEXT NOT NULL,
                placeholders_json TEXT NOT NULL DEFAULT '[]',
                when_to_use     TEXT NOT NULL DEFAULT '',
                tags            TEXT NOT NULL DEFAULT '',
                references_links TEXT NOT NULL DEFAULT '',
                first_seen      INTEGER NOT NULL,
                last_seen       INTEGER NOT NULL,
                use_count       INTEGER NOT NULL DEFAULT 0,
                embed_text      TEXT NOT NULL DEFAULT ''
            )
            """
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_prompts_category ON prompts(category)"
        )
        c.execute(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS prompts_vec USING vec0(
                embedding float[{EMBED_DIM}]
            )
            """
        )
        # sqlite-vec virtual tables — one per searchable surface.  rowid in
        # the vec table aligns with rowid in the source table.
        c.execute(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS anti_patterns_vec USING vec0(
                embedding float[{EMBED_DIM}]
            )
            """
        )
        c.execute(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS script_vec USING vec0(
                embedding float[{EMBED_DIM}]
            )
            """
        )
        # ---- Delegates (local-resource registry) -----------------------
        # A delegate is a non-Claude compute resource we can defer work to:
        # local LLM, MetaMCP server, a remote shell on a beefy box, etc.
        # contact_json holds the contact recipe (HTTP URL, SSH host+user,
        # protocol hint, optional auth-header name).  Keeping it JSON means
        # future delegate kinds don't need a schema migration.
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS delegates (
                id                TEXT PRIMARY KEY,
                name              TEXT NOT NULL UNIQUE,
                kind              TEXT NOT NULL,
                contact_json      TEXT NOT NULL DEFAULT '{}',
                capabilities_json TEXT NOT NULL DEFAULT '[]',
                notes             TEXT NOT NULL DEFAULT '',
                added_at          INTEGER NOT NULL,
                enabled           INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        # Every delegation attempt: success / partial / failure / refused +
        # latency + capability tag + free-text task summary.  Aggregated
        # into per-capability success-rate / median-latency stats by the
        # /delegates endpoint so callers can pick the best delegate for a
        # capability or decide it isn't worth deferring at all.
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS delegation_log (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                delegate_id   TEXT NOT NULL,
                capability    TEXT NOT NULL,
                task_summary  TEXT NOT NULL,
                outcome       TEXT NOT NULL CHECK(outcome IN ('success','partial','failure','refused')),
                latency_ms    INTEGER,
                token_savings INTEGER,
                notes         TEXT NOT NULL DEFAULT '',
                ts_unix_ms    INTEGER NOT NULL,
                FOREIGN KEY (delegate_id) REFERENCES delegates(id)
            )
            """
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_deleg_log_delegate_capability "
            "ON delegation_log(delegate_id, capability)"
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_deleg_log_ts "
            "ON delegation_log(ts_unix_ms DESC)"
        )


_init_schema()


def _seed_known_delegates() -> None:
    """Seed the registry with the delegates the user has already told us
    about.  Only inserts if the row is missing — never overwrites human
    edits.  Endpoint details start as TBD placeholders so the row exists
    and can be searched even before the user fills in the URL."""
    with _conn() as c:
        for delegate in _SEED_DELEGATES:
            row = c.execute(
                "SELECT id FROM delegates WHERE name = ?", (delegate["name"],)
            ).fetchone()
            if row:
                continue
            c.execute(
                "INSERT INTO delegates (id, name, kind, contact_json, "
                "capabilities_json, notes, added_at, enabled) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    uuid.uuid4().hex,
                    delegate["name"],
                    delegate["kind"],
                    json.dumps(delegate["contact"], sort_keys=True),
                    json.dumps(delegate["capabilities"], sort_keys=True),
                    delegate["notes"],
                    int(time.time()),
                    1 if delegate.get("enabled", True) else 0,
                ),
            )


# Rote ships with NO preloaded delegates — a delegate is a piece of compute
# YOU own (a local LLM, an MCP aggregator, an SSH-reachable box), so the
# registry starts empty and you register your own with a POST /delegates, e.g.:
#
#   curl -s http://127.0.0.1:5572/delegates -H 'content-type: application/json' \
#     -d '{"name":"local-llm","kind":"llm",
#          "contact":{"protocol":"openai-compatible","url":"http://localhost:11434/v1"},
#          "capabilities":["bulk-summarization","log-skim","doc-skim"],
#          "enabled":true}'
#
# then `rote delegate enable local-llm`. The shape of a seed row, if you would
# rather preload one here, is:
#
#   {
#       "name": "local-llm",
#       "kind": "llm",                       # llm | mcp | ssh
#       "contact": {
#           "protocol": "openai-compatible",
#           "url": "http://localhost:11434/v1",
#           "ssh": {"user": "you", "host": "your-box"},  # optional
#           "auth_header": None,             # vault key name, never a value
#       },
#       "capabilities": ["bulk-summarization", "log-skim", "doc-skim"],
#       "notes": "...",
#       "enabled": False,                    # flip on after a /healthz probe
#   }
_SEED_DELEGATES: list[dict[str, Any]] = []

_seed_known_delegates()


def _audit(kind: str, payload: dict[str, Any]) -> None:
    """Append an audit row.  Names + counts only — never secret bytes."""
    with _conn() as c:
        c.execute(
            "INSERT INTO audit_log (ts_unix_ms, kind, payload_json) VALUES (?, ?, ?)",
            (int(time.time() * 1000), kind, json.dumps(payload, sort_keys=True)),
        )


# ---------------------------------------------------------------------------
# Embedding model.
#
# Two backends, picked by env var at startup so we can shed the 80 MB
# torch + sentence-transformers dep when an Ollama embedding endpoint is
# reachable.
#
#   OLLAMA_EMBED_URL=http://localhost:11434  → use Ollama's
#                                                 nomic-embed-text (HTTP)
#   (unset)                                     → sentence-transformers
#                                                 all-MiniLM-L6-v2 (local)
#
# Both produce 384-dim float vectors so existing vec0 rows are compatible
# (nomic-embed-text returns 768-dim; we mean-pool down to 384 client-side
# so the dimensionality matches the existing schema without a migration).
#
# Lazy-loaded — embedding work doesn't pay cold-start cost on /healthz or
# vault reads.
# ---------------------------------------------------------------------------
import os as _os
_embed_lock = Lock()
_embed_model: Any = None

OLLAMA_EMBED_URL = _os.environ.get("OLLAMA_EMBED_URL", "").rstrip("/")
OLLAMA_EMBED_MODEL = _os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")


def _embed_via_st(text: str) -> list[float]:
    global _embed_model
    with _embed_lock:
        if _embed_model is None:
            from sentence_transformers import SentenceTransformer  # type: ignore

            _embed_model = SentenceTransformer(EMBED_MODEL_NAME)
    return _embed_model.encode([text], normalize_embeddings=True)[0].tolist()


def _embed_via_ollama(text: str) -> list[float]:
    """Call Ollama's /api/embeddings.  nomic-embed-text returns 768-dim;
    we mean-pool adjacent pairs down to 384 so the wire-format matches the
    existing sqlite-vec schema without a destructive migration.

    This is a deliberately-naive dim-reduction.  For higher-quality search
    when this backend is in primary use, change EMBED_DIM to 768 and
    regenerate the script_vec / anti_patterns_vec tables (DELETE FROM …).
    """
    import urllib.request

    req = urllib.request.Request(
        f"{OLLAMA_EMBED_URL}/api/embeddings",
        data=json.dumps({"model": OLLAMA_EMBED_MODEL, "prompt": text}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode())
    raw = body.get("embedding") or []
    if not raw:
        raise RuntimeError(f"Ollama embeddings returned no vector for model {OLLAMA_EMBED_MODEL}")
    if len(raw) == EMBED_DIM:
        return list(raw)
    # Mean-pool down to EMBED_DIM.
    chunk = max(1, len(raw) // EMBED_DIM)
    out: list[float] = []
    for i in range(EMBED_DIM):
        slice_ = raw[i * chunk : (i + 1) * chunk]
        if not slice_:
            out.append(0.0)
        else:
            out.append(sum(slice_) / len(slice_))
    # L2 normalize.
    norm = (sum(v * v for v in out)) ** 0.5 or 1.0
    return [v / norm for v in out]


def _embed_model_get() -> Any:
    """Compatibility shim — kept so /healthz can report a model name.
    Returns a sentinel string when Ollama backend is active."""
    if OLLAMA_EMBED_URL:
        return f"ollama:{OLLAMA_EMBED_MODEL}@{OLLAMA_EMBED_URL}"
    # Force the lazy ST load.
    with _embed_lock:
        if _embed_model is None:
            from sentence_transformers import SentenceTransformer  # type: ignore

            _ = SentenceTransformer  # touched for healthz signal
    return EMBED_MODEL_NAME


_EMBED_BACKEND_DOWN = False


def _embed(text: str) -> bytes:
    """Return the float32 little-endian byte buffer sqlite-vec wants.

    Degrades to a zero vector when the embedding backend (Ollama on the
    configured host) is unreachable, so list / index / GUI endpoints keep
    working offline instead of 500-ing. Rows embedded while the backend was
    down get a zero vector (poor semantic-search match); re-touch the file or
    restart with the backend reachable to re-embed.
    """
    global _EMBED_BACKEND_DOWN
    try:
        vec = _embed_via_ollama(text) if OLLAMA_EMBED_URL else _embed_via_st(text)
        _EMBED_BACKEND_DOWN = False
    except Exception:
        _EMBED_BACKEND_DOWN = True
        vec = [0.0] * EMBED_DIM
    return struct.pack(f"{EMBED_DIM}f", *vec)


# ---------------------------------------------------------------------------
# GUI — minimal single-page explorer for humans.  Pure HTML + vanilla JS, no
# frameworks or external CDN dependencies so the GUI works the same offline
# as online and survives any web blocklist.
# ---------------------------------------------------------------------------
_GUI_HTML = """<!doctype html>
<html lang=en>
<head>
<meta charset=utf-8>
<title>rote</title>
<style>
*{box-sizing:border-box}
html,body{margin:0;font:14px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;background:#0f1115;color:#e6edf3}
header{padding:.6rem 1rem;background:#161b22;border-bottom:1px solid #30363d;display:flex;gap:1rem;align-items:center}
header h1{margin:0;font-size:1rem;color:#7ee787}
nav{display:flex;gap:.4rem}
nav button{background:transparent;color:#e6edf3;border:1px solid #30363d;padding:.3rem .6rem;cursor:pointer;font:inherit;border-radius:3px}
nav button.active{background:#1f6feb;border-color:#1f6feb}
main{padding:1rem;max-width:1200px;margin:0 auto}
section{display:none}
section.active{display:block}
input[type=search]{width:100%;padding:.5rem;background:#0d1117;color:#e6edf3;border:1px solid #30363d;border-radius:3px;font:inherit;margin-bottom:.8rem}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:.4rem .6rem;border-bottom:1px solid #21262d;text-align:left;vertical-align:top}
th{color:#7d8590;font-weight:normal;font-size:11px;text-transform:uppercase;letter-spacing:.05em}
tr:hover td{background:#161b22}
.tag{display:inline-block;font-size:11px;padding:1px 6px;border-radius:3px;background:#21262d;color:#7d8590}
.tag.secret{background:#3d1f1f;color:#f85149}
.dim{color:#7d8590}
.mono{font-family:inherit}
.empty{color:#7d8590;font-style:italic;padding:1rem 0}
pre.audit{background:#0d1117;border:1px solid #21262d;border-radius:3px;padding:.6rem;overflow-x:auto;font-size:12px;max-height:60vh}
.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:.7rem;margin-bottom:1rem}
.tile{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:.8rem 1rem;display:flex;flex-direction:column;gap:.2rem}
.tile .label{font-size:11px;color:#7d8590;text-transform:uppercase;letter-spacing:.05em}
.tile .value{font-size:1.7rem;color:#7ee787;font-weight:600;line-height:1.1}
.tile .sub{font-size:11px;color:#7d8590}
.tile.lifetime .value{color:#a5d6ff}
.spark{background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:.8rem 1rem;margin-bottom:1rem}
.spark-head{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:.4rem}
.spark-head .title{font-size:11px;color:#7d8590;text-transform:uppercase;letter-spacing:.05em}
.spark-head .meta{font-size:11px;color:#7d8590}
.spark svg{width:100%;height:60px;display:block}
.spark .axis{stroke:#30363d;stroke-width:1}
.spark .bar{fill:#1f6feb}
.spark .bar.zero{fill:#21262d}
.tokens-grid{display:grid;grid-template-columns:1fr 1fr;gap:1rem}
.tokens-grid h3{margin:.2rem 0 .5rem;font-size:13px;color:#7d8590;text-transform:uppercase;letter-spacing:.05em;font-weight:normal}
.tokens-grid table{font-size:12px}
.num{text-align:right;font-variant-numeric:tabular-nums}
@media (max-width:800px){.tiles{grid-template-columns:repeat(2,1fr)}.tokens-grid{grid-template-columns:1fr}}
td.act{white-space:nowrap;text-align:right}
button.act{background:#21262d;color:#e6edf3;border:1px solid #30363d;padding:1px 7px;cursor:pointer;font:inherit;font-size:12px;border-radius:3px;margin-left:3px}
button.act:hover{background:#30363d}
button.act.danger:hover{background:#3d1f1f;border-color:#f85149;color:#f85149}
button.toggle{min-width:42px}
.modal-bg{position:fixed;inset:0;background:rgba(0,0,0,.65);display:none;align-items:center;justify-content:center;z-index:10}
.modal-bg.open{display:flex}
.modal{background:#0d1117;border:1px solid #30363d;border-radius:6px;width:min(920px,93vw);max-height:90vh;display:flex;flex-direction:column;padding:1rem}
.modal h3{margin:.1rem 0 .6rem;font-size:13px;color:#7ee787;word-break:break-all}
.modal textarea{width:100%;flex:1;min-height:48vh;background:#0d1117;color:#e6edf3;border:1px solid #30363d;border-radius:3px;font:12px/1.45 ui-monospace,monospace;padding:.6rem;resize:vertical}
.modal .reveal{font:12px/1.45 ui-monospace,monospace;background:#161b22;border:1px solid #30363d;border-radius:3px;padding:.6rem;word-break:break-all;color:#f0b72f;max-height:40vh;overflow:auto}
.modal .row{display:flex;gap:.5rem;justify-content:flex-end;margin-top:.6rem}
.pager{display:flex;gap:.5rem;align-items:center;margin-top:.6rem;font-size:12px;color:#7d8590}
.pager button{background:#21262d;color:#e6edf3;border:1px solid #30363d;padding:2px 9px;cursor:pointer;border-radius:3px;font:inherit}
.pager button:disabled{opacity:.4;cursor:default}
#toast{position:fixed;bottom:1rem;left:50%;transform:translateX(-50%);background:#1f6feb;color:#fff;padding:.4rem .9rem;border-radius:4px;font-size:12px;display:none;z-index:20}
#toast.err{background:#f85149}
</style>
</head>
<body>
<header>
<h1>rote</h1>
<nav>
<button data-tab=scripts class=active>scripts</button>
<button data-tab=patterns>patterns</button>
<button data-tab=tech>tech</button>
<button data-tab=snippets>snippets</button>
<button data-tab=commands>commands</button>
<button data-tab=stacks>stacks</button>
<button data-tab=antipatterns>anti-patterns</button>
<button data-tab=delegates>delegates</button>
<button data-tab=tokens>tokens saved</button>
<button data-tab=vault>vault</button>
<button data-tab=audit>audit</button>
</nav>
<span id=health class=dim style=margin-left:auto></span>
</header>
<main>
<section id=scripts class=active>
<input type=search id=scripts-q placeholder='semantic search — e.g. "inject env secrets"'>
<table id=scripts-table><thead><tr><th>name<th>secrets<th>runs<th>fail<th>purpose<th></tr></thead><tbody></tbody></table>
<p id=scripts-empty class='empty' hidden>no scripts yet — drop .sh files in the scripts/ directory</p>
<div class=pager id=scripts-pager hidden><button id=scripts-prev>prev</button><span id=scripts-range></span><button id=scripts-next>next</button><span style=margin-left:auto><button class=act id=scripts-new>+ new script</button></span></div>
</section>
<section id=patterns>
<input type=search id=patterns-q placeholder='semantic search design patterns (e.g. "safe retry remote calls")'>
<table id=patterns-table><thead><tr><th>slug<th>category<th>uses<th>intent<th></tr></thead><tbody></tbody></table>
<p id=patterns-empty class='empty' hidden>no design patterns indexed — re-run scripts/seed-design-patterns-and-technologies.py</p>
</section>
<section id=tech>
<input type=search id=tech-q placeholder='semantic search technologies (e.g. "offline-capable pub/sub broker")'>
<table id=tech-table><thead><tr><th>slug<th>category<th>tags<th>limitations summary<th></tr></thead><tbody></tbody></table>
<p id=tech-empty class='empty' hidden>no technologies indexed</p>
</section>
<section id=snippets>
<input type=search id=snippets-q placeholder='semantic search snippets (e.g. "Polly retry circuit breaker")'>
<table id=snippets-table><thead><tr><th>slug<th>lang<th>uses<th>placeholders<th>when_to_use<th></tr></thead><tbody></tbody></table>
<p id=snippets-empty class='empty' hidden>no snippets indexed</p>
</section>
<section id=commands>
<input type=search id=commands-q placeholder='semantic search commands (e.g. "install package in Dockerfile" or "follow systemd logs")'>
<table id=commands-table><thead><tr><th>slug<th>family<th>uses<th>command_line<th></tr></thead><tbody></tbody></table>
<p id=commands-empty class='empty' hidden>no commands indexed</p>
</section>
<section id=stacks>
<input type=search id=stacks-q placeholder='semantic search stacks (e.g. "offline-capable broker")'>
<table id=stacks-table><thead><tr><th>slug<th>outcome<th>technologies<th>context<th></tr></thead><tbody></tbody></table>
<p id=stacks-empty class='empty' hidden>no stacks recorded yet</p>
</section>
<section id=antipatterns>
<input type=search id=ap-q placeholder='semantic search by symptom'>
<table id=ap-table><thead><tr><th>slug<th>hits<th>title<th>remedy<th></tr></thead><tbody></tbody></table>
<p id=ap-empty class='empty' hidden>no anti-patterns recorded yet — chronicle skill seeds them on session post-mortems</p>
</section>
<section id=delegates>
<p class='dim'>local resources Claude can defer work to (LLMs, MetaMCP servers, SSH hosts). Stats are derived from the per-delegation outcome log — defer only to capabilities a delegate has proven on.</p>
<table id=delegates-table><thead><tr><th>name<th>kind<th>enabled<th>capabilities (success / n)<th>contact<th></tr></thead><tbody></tbody></table>
<p id=delegates-empty class='empty' hidden>no delegates registered — POST /delegates or seed via the API</p>
<h3 style='margin-top:1.5rem;font-size:13px;color:#7d8590;text-transform:uppercase;letter-spacing:.05em'>recent delegations</h3>
<pre class=audit id=delegations-body></pre>
</section>
<section id=tokens>
<p class='dim'>tokens deferred from Claude's context to local delegates (Ollama / sglang / MCP). Numbers are best-effort estimates the dispatcher logs at call time — useful ballpark, not a billing source of truth.</p>
<div class=tiles>
  <div class='tile lifetime'><span class=label>lifetime saved</span><span class='value' id=tok-lifetime>—</span><span class=sub id=tok-lifetime-sub></span></div>
  <div class=tile><span class=label>last 24h</span><span class='value' id=tok-24h>—</span><span class=sub id=tok-24h-sub></span></div>
  <div class=tile><span class=label>last 7d</span><span class='value' id=tok-7d>—</span><span class=sub id=tok-7d-sub></span></div>
  <div class=tile><span class=label>last 30d</span><span class='value' id=tok-30d>—</span><span class=sub id=tok-30d-sub></span></div>
</div>
<div class=spark>
  <div class=spark-head><span class=title>daily tokens saved — last 30 days</span><span class=meta id=spark-meta></span></div>
  <svg id=spark-svg viewBox='0 0 600 60' preserveAspectRatio='none'></svg>
</div>
<div class=tokens-grid>
  <div>
    <h3>per delegate</h3>
    <table id=tokens-by-delegate><thead><tr><th>name<th class=num>saved<th class=num>calls<th class=num>success</tr></thead><tbody></tbody></table>
    <p id=tok-del-empty class='empty' hidden>no delegations logged yet</p>
  </div>
  <div>
    <h3>per capability</h3>
    <table id=tokens-by-capability><thead><tr><th>capability<th class=num>saved<th class=num>calls<th class=num>success</tr></thead><tbody></tbody></table>
    <p id=tok-cap-empty class='empty' hidden>no delegations logged yet</p>
  </div>
</div>
</section>
<section id=vault>
<p class='dim'>names + byte sizes only. values never leave the server.</p>
<table id=vault-table><thead><tr><th>name<th>bytes<th></tr></thead><tbody></tbody></table>
<p id=vault-empty class='empty' hidden>vault is empty — populate secret-vault/secrets.json</p>
</section>
<section id=audit>
<p class='dim'>recent 100 events. key names + counts only — never bytes.</p>
<pre class=audit id=audit-body></pre>
</section>
</main>
<div class=modal-bg id=modal><div class=modal>
<h3 id=modal-title></h3>
<textarea id=modal-text spellcheck=false hidden></textarea>
<div id=modal-reveal class=reveal hidden></div>
<div class=row>
<button class=act id=modal-copy hidden>copy</button>
<button class=act id=modal-save hidden>save</button>
<button class=act id=modal-close>close</button>
</div>
</div></div>
<div id=toast></div>
<script>
const API = '';
const $ = s => document.querySelector(s);
const j = (m,p,b) => fetch(API+p,{method:m,headers:{'content-type':'application/json'},body:b?JSON.stringify(b):undefined}).then(r=>r.json());

// ---- shared UI helpers (added 2026-06-17) ----
const debounce = (fn,ms) => { let t; return (...a) => { clearTimeout(t); t=setTimeout(()=>fn(...a),ms); }; };
let toastT;
function toast(msg,isErr){ const el=$('#toast'); el.textContent=msg; el.className=isErr?'err':''; el.style.display='block'; clearTimeout(toastT); toastT=setTimeout(()=>el.style.display='none',2200); }
async function copyText(t){ try{ await navigator.clipboard.writeText(t); toast('copied'); }catch(e){ toast('copy failed',1); } }

// Per-tab cache of the full list so search-stat-folding doesn't re-GET the whole
// list (and re-trigger the drvfs reindex / embed) on every keystroke.
const cache = {};
function invalidate(k){ delete cache[k]; }
function fullList(key,path,field){ if(!cache[key]) cache[key]=j('GET',path).then(r=>r[field]||[]); return cache[key]; }

// Modal: view (read-only), edit (textarea + save), or reveal (secret value + copy).
let modalSave=null, modalCopyVal=null;
function showModal(title,{text='',editable=false,reveal=false,onSave=null,copyVal=null}={}){
    $('#modal-title').textContent=title;
    const ta=$('#modal-text'), rv=$('#modal-reveal');
    if(reveal){ ta.hidden=true; rv.hidden=false; rv.textContent=text; }
    else { rv.hidden=true; ta.hidden=false; ta.value=text; ta.readOnly=!editable; }
    $('#modal-save').hidden=!editable; modalSave=onSave;
    modalCopyVal = copyVal!==null ? copyVal : (reveal?text:(editable?null:text));
    $('#modal-copy').hidden = modalCopyVal===null;
    $('#modal').classList.add('open');
}
function closeModal(){ $('#modal').classList.remove('open'); modalSave=null; modalCopyVal=null; }
$('#modal-close').onclick=closeModal;
$('#modal').onclick=e=>{ if(e.target===$('#modal')) closeModal(); };
$('#modal-copy').onclick=()=>{ if(modalCopyVal!=null) copyText($('#modal-text').hidden?$('#modal-reveal').textContent:$('#modal-text').value); };
$('#modal-save').onclick=async()=>{ if(modalSave){ await modalSave($('#modal-text').value); closeModal(); } };

async function delItem(label,path,key,reload){
    if(!confirm('Delete '+label+'?\\nThis cannot be undone.')) return;
    const r=await j('DELETE',path);
    if(r && r.action){ toast(label+' deleted'); invalidate(key); reload(); }
    else { toast((r&&r.detail)||'delete failed',1); }
}

document.querySelectorAll('nav button').forEach(btn => btn.onclick = () => {
    document.querySelectorAll('nav button').forEach(b => b.classList.toggle('active', b===btn));
    document.querySelectorAll('section').forEach(s => s.classList.toggle('active', s.id===btn.dataset.tab));
    load(btn.dataset.tab);
});

let scriptsPage = 0; const SCRIPTS_PAGE = 50;
async function loadScripts(query) {
    let items, total, start = 0;
    if (query) {
        const matches = (await j('POST','/scripts/search',{query,limit:20})).matches;
        // fold stats from the cached full list (no re-GET per keystroke)
        const full = await fullList('scripts','/scripts','scripts');
        const byName = Object.fromEntries(full.map(s => [s.name, s]));
        items = matches.map(m => ({...byName[m.name], d: m.distance.toFixed(3)}));
        total = items.length;
        $('#scripts-pager').hidden = true;
    } else {
        const r = await j('GET',`/scripts?limit=${SCRIPTS_PAGE}&offset=${scriptsPage*SCRIPTS_PAGE}`);
        items = r.scripts; total = r.total; start = r.offset;
        const end = start + items.length;
        $('#scripts-range').textContent = total ? `${start+1}–${end} of ${total}` : '0';
        $('#scripts-prev').disabled = start===0;
        $('#scripts-next').disabled = end>=total;
        $('#scripts-pager').hidden = false;
    }
    const tb = $('#scripts-table tbody'); tb.innerHTML='';
    $('#scripts-empty').hidden = items.length>0;
    for (const s of items) {
        const tr = document.createElement('tr');
        const secret = s.touches_secrets==='true' || (s.touches_secrets||'').startsWith('true')
            ? '<span class="tag secret">secrets</span>'
            : '<span class=tag>safe</span>';
        const st = s.stats || {};
        const runs = st.run_count || 0;
        const fail = st.failure_count || 0;
        const rate = st.success_rate;
        let fail_chip;
        if (runs === 0) {
            fail_chip = '<span class=dim>—</span>';
        } else if (fail === 0) {
            fail_chip = '<span class=tag>0</span>';
        } else if (rate >= 0.7) {
            fail_chip = `<span class=tag>${fail}/${runs}</span>`;
        } else {
            fail_chip = `<span class="tag secret">${fail}/${runs}</span>`;
        }
        const runs_chip = runs > 0 ? `<span class=tag>${runs}</span>` : '<span class=dim>—</span>';
        const acts = `<button class=act data-act=view data-id="${esc(s.name)}">view</button>`
            + `<button class=act data-act=edit data-id="${esc(s.name)}">edit</button>`
            + `<button class="act danger" data-act=del data-id="${esc(s.name)}">del</button>`;
        tr.innerHTML = `<td class=mono>${esc(s.name)}${s.d?' <span class=dim>d='+s.d+'</span>':''}<td>${secret}<td>${runs_chip}<td>${fail_chip}<td>${esc(s.purpose||'')}<td class=act>${acts}`;
        tb.appendChild(tr);
    }
}

// scripts row actions + pager + new
async function viewScript(name, edit) {
    const r = await j('GET','/scripts/'+encodeURIComponent(name)+'/content');
    if(r.detail){ toast(r.detail,1); return; }
    showModal((edit?'edit · ':'view · ')+name,{text:r.content,editable:!!edit,onSave:async(content)=>{
        const res=await j('PUT','/scripts/'+encodeURIComponent(name),{content});
        if(res.action){ toast('saved'); invalidate('scripts'); loadScripts($('#scripts-q').value); }
        else toast((res.detail)||'save failed',1);
    }});
}
$('#scripts-table tbody').onclick = e => {
    const b=e.target.closest('button[data-act]'); if(!b) return;
    const id=b.dataset.id;
    if(b.dataset.act==='view') viewScript(id,false);
    else if(b.dataset.act==='edit') viewScript(id,true);
    else if(b.dataset.act==='del') delItem('script '+id,'/scripts/'+encodeURIComponent(id),'scripts',()=>loadScripts($('#scripts-q').value));
};
$('#scripts-prev').onclick=()=>{ if(scriptsPage>0){scriptsPage--; loadScripts('');} };
$('#scripts-next').onclick=()=>{ scriptsPage++; loadScripts(''); };
$('#scripts-new').onclick=()=>showModal('new script (filename set by first line comment is ignored — name it)',{text:'#!/usr/bin/env bash\\n',editable:true,onSave:async(content)=>{
    const name=prompt('script filename (e.g. my-thing.sh):'); if(!name) return;
    const res=await j('PUT','/scripts/'+encodeURIComponent(name),{content});
    if(res.action){ toast('created '+name); invalidate('scripts'); loadScripts(''); } else toast((res.detail)||'create failed',1);
}});

async function loadAP(query) {
    let items;
    if (query) {
        items = (await j('POST','/anti-patterns/search',{query,limit:20})).matches.map(m=>({...m,d:m.distance.toFixed(3)}));
    } else {
        items = (await j('GET','/anti-patterns')).anti_patterns;
    }
    const tb = $('#ap-table tbody'); tb.innerHTML='';
    $('#ap-empty').hidden = items.length>0;
    for (const a of items) {
        const tr = document.createElement('tr');
        const acts = `<button class="act danger" data-act=del data-id="${esc(a.slug)}">del</button>`;
        tr.innerHTML = `<td class=mono>${esc(a.slug)}${a.d?' <span class=dim>d='+a.d+'</span>':''}<td>${a.hit_count||1}<td>${esc(a.title)}<td class=dim>${esc(a.remedy)}<td class=act>${acts}`;
        tb.appendChild(tr);
    }
}
$('#ap-table tbody').onclick = e => {
    const b=e.target.closest('button[data-act=del]'); if(!b) return;
    delItem('anti-pattern '+b.dataset.id,'/anti-patterns/'+encodeURIComponent(b.dataset.id),'ap',()=>loadAP($('#ap-q').value));
};

async function loadVault() {
    const items = (await j('GET','/vault/keys')).keys;
    const tb = $('#vault-table tbody'); tb.innerHTML='';
    $('#vault-empty').hidden = items.length>0;
    for (const k of items) {
        const tr = document.createElement('tr');
        const acts = `<button class=act data-act=reveal data-id="${esc(k.name)}">reveal</button>`
            + `<button class="act danger" data-act=del data-id="${esc(k.name)}">del</button>`;
        tr.innerHTML = `<td class=mono>${esc(k.name)}<td>${k.bytes}<td class=act>${acts}`;
        tb.appendChild(tr);
    }
}
$('#vault-table tbody').onclick = async e => {
    const b=e.target.closest('button[data-act]'); if(!b) return;
    const key=b.dataset.id;
    if(b.dataset.act==='reveal'){
        const r=await j('GET','/vault/'+encodeURIComponent(key)+'/reveal');
        if(r.value!==undefined) showModal('secret · '+key,{text:r.value,reveal:true});
        else toast((r.detail)||'reveal failed',1);
    } else {
        delItem('secret '+key,'/vault/'+encodeURIComponent(key),'vault',loadVault);
    }
};

async function loadAudit() {
    const items = (await j('GET','/audit?limit=100')).events;
    $('#audit-body').textContent = items.map(e=>{
        const t = new Date(e.ts_unix_ms).toISOString().slice(11,19);
        return t+' '+e.kind+' '+JSON.stringify(e.payload);
    }).join('\\n');
}

async function loadDelegates() {
    const items = (await j('GET','/delegates')).delegates;
    const tb = $('#delegates-table tbody'); tb.innerHTML='';
    $('#delegates-empty').hidden = items.length>0;
    for (const d of items) {
        const tr = document.createElement('tr');
        const caps_str = d.capabilities.map(c => {
            const s = (d.stats?.per_capability||[]).find(x=>x.capability===c);
            if (!s) return `${esc(c)} <span class=dim>(0)</span>`;
            const rate = (s.success_rate*100).toFixed(0);
            const tag_class = s.success_rate >= 0.7 ? 'tag' : (s.success_rate >= 0.4 ? 'tag' : 'tag secret');
            return `<span class='${tag_class}'>${esc(c)} ${rate}% / ${s.n}</span>`;
        }).join(' ');
        const contact = d.contact || {};
        const contact_str = contact.url || (contact.ssh ? `ssh ${contact.ssh.user}@${contact.ssh.host}` : '<span class=dim>—</span>');
        const tog = `<button class="act toggle" data-act=toggle data-id="${esc(d.name)}" data-on="${d.enabled?1:0}">${d.enabled?'on':'off'}</button>`;
        const acts = `<button class="act danger" data-act=del data-id="${esc(d.name)}">del</button>`;
        tr.innerHTML = `<td class=mono>${esc(d.name)}<td>${esc(d.kind)}<td>${tog}<td>${caps_str||'<span class=dim>—</span>'}<td class=mono>${esc(contact_str)}<td class=act>${acts}`;
        tb.appendChild(tr);
    }
    // Recent delegations
    const log = (await j('GET','/delegations?limit=25')).events;
    $('#delegations-body').textContent = log.length ? log.map(e=>{
        const t = new Date(e.ts_unix_ms).toISOString().slice(0,16).replace('T',' ');
        const lat = e.latency_ms ? ` ${e.latency_ms}ms` : '';
        const tok = e.token_savings ? ` saved=${e.token_savings}t` : '';
        return `${t} ${e.delegate} ${e.capability} ${e.outcome}${lat}${tok} — ${e.task_summary}`;
    }).join('\\n') : '(no delegations logged yet)';
}
$('#delegates-table tbody').onclick = async e => {
    const b=e.target.closest('button[data-act]'); if(!b) return;
    const name=b.dataset.id;
    if(b.dataset.act==='toggle'){
        const on=b.dataset.on==='1';
        const r=await j('PATCH','/delegates/'+encodeURIComponent(name),{enabled:!on});
        if(r.action){ toast('delegate '+(on?'disabled':'enabled')); loadDelegates(); } else toast((r.detail)||'toggle failed',1);
    } else {
        delItem('delegate '+name,'/delegates/'+encodeURIComponent(name),'delegates',loadDelegates);
    }
};

function esc(s) { return (s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[c]); }

async function loadPatterns(query) {
    let items;
    if (query) {
        const matches = (await j('POST','/design-patterns/search',{query,limit:20})).matches;
        const full = (await j('GET','/design-patterns')).design_patterns;
        const byName = Object.fromEntries(full.map(p => [p.slug, p]));
        items = matches.map(m => ({...byName[m.slug], d: m.distance.toFixed(3)}));
    } else {
        items = (await j('GET','/design-patterns')).design_patterns;
    }
    const tb = $('#patterns-table tbody'); tb.innerHTML='';
    $('#patterns-empty').hidden = items.length>0;
    for (const p of items) {
        const tr = document.createElement('tr');
        const uses = p.use_count>0 ? `<span class=tag>${p.use_count}</span>` : '<span class=dim>—</span>';
        tr.innerHTML = `<td class=mono>${esc(p.slug)}${p.d?' <span class=dim>d='+p.d+'</span>':''}<td><span class=tag>${esc(p.category||'')}</span><td>${uses}<td>${esc(p.intent||'')}<td class=act><button class=act data-act=view data-id="${esc(p.slug)}">view</button><button class="act danger" data-act=del data-id="${esc(p.slug)}">del</button>`;
        tb.appendChild(tr);
    }
}

async function loadTech(query) {
    let items;
    if (query) {
        const matches = (await j('POST','/technologies/search',{query,limit:20})).matches;
        const full = (await j('GET','/technologies')).technologies;
        const byName = Object.fromEntries(full.map(t => [t.slug, t]));
        items = matches.map(m => ({...byName[m.slug], d: m.distance.toFixed(3)}));
    } else {
        items = (await j('GET','/technologies')).technologies;
    }
    const tb = $('#tech-table tbody'); tb.innerHTML='';
    $('#tech-empty').hidden = items.length>0;
    for (const t of items) {
        const tr = document.createElement('tr');
        const tags = (t.tags||'').split(',').map(x=>x.trim()).filter(Boolean).map(tag => {
            const cls = (tag==='cloud-only' || tag==='vendor-locked' || tag==='no-offline') ? 'tag secret' : 'tag';
            return `<span class='${cls}'>${esc(tag)}</span>`;
        }).join(' ');
        const lim = (t.limitations||'').split('\\n').filter(l=>l.trim()).slice(0,1).join(' ');
        tr.innerHTML = `<td class=mono>${esc(t.slug)}${t.d?' <span class=dim>d='+t.d+'</span>':''}<td><span class=tag>${esc(t.category||'')}</span><td>${tags}<td class=dim>${esc(lim)}<td class=act><button class=act data-act=view data-id="${esc(t.slug)}">view</button><button class="act danger" data-act=del data-id="${esc(t.slug)}">del</button>`;
        tb.appendChild(tr);
    }
}

async function loadSnippets(query) {
    let items;
    if (query) {
        const matches = (await j('POST','/snippets/search',{query,limit:20})).matches;
        const full = (await j('GET','/snippets')).snippets;
        const byName = Object.fromEntries(full.map(s => [s.slug, s]));
        items = matches.map(m => ({...byName[m.slug], d: m.distance.toFixed(3)}));
    } else {
        items = (await j('GET','/snippets')).snippets;
    }
    const tb = $('#snippets-table tbody'); tb.innerHTML='';
    $('#snippets-empty').hidden = items.length>0;
    for (const s of items) {
        const tr = document.createElement('tr');
        const uses = s.use_count>0 ? `<span class=tag>${s.use_count}</span>` : '<span class=dim>—</span>';
        const ph_count = (s.placeholders||[]).length;
        const ph_label = ph_count>0 ? `<span class=tag>${ph_count}</span>` : '<span class=dim>—</span>';
        const when_short = (s.when_to_use||'').split('\\n').filter(l=>l.trim()).slice(0,1).join(' ');
        tr.innerHTML = `<td class=mono>${esc(s.slug)}${s.d?' <span class=dim>d='+s.d+'</span>':''}<td><span class=tag>${esc(s.language||'')}</span><td>${uses}<td>${ph_label}<td class=dim>${esc(when_short)}<td class=act><button class=act data-act=copy data-id="${esc(s.slug)}">copy</button><button class=act data-act=view data-id="${esc(s.slug)}">view</button><button class="act danger" data-act=del data-id="${esc(s.slug)}">del</button>`;
        tb.appendChild(tr);
    }
}

async function loadStacks(query) {
    let items;
    if (query) {
        const matches = (await j('POST','/stacks/search',{query,limit:20})).matches;
        const full = (await j('GET','/stacks')).stacks;
        const byName = Object.fromEntries(full.map(s => [s.slug, s]));
        items = matches.map(m => ({...byName[m.slug], d: m.distance.toFixed(3)}));
    } else {
        items = (await j('GET','/stacks')).stacks;
    }
    const tb = $('#stacks-table tbody'); tb.innerHTML='';
    $('#stacks-empty').hidden = items.length>0;
    for (const s of items) {
        const tr = document.createElement('tr');
        let outcome_chip;
        if (s.outcome==='success') outcome_chip = '<span class=tag>success</span>';
        else if (s.outcome==='failure') outcome_chip = '<span class="tag secret">failure</span>';
        else outcome_chip = `<span class=tag>${esc(s.outcome||'')}</span>`;
        tr.innerHTML = `<td class=mono>${esc(s.slug)}${s.d?' <span class=dim>d='+s.d+'</span>':''}<td>${outcome_chip}<td class=mono>${esc(s.technologies||'')}<td class=dim>${esc(s.context||'')}<td class=act><button class=act data-act=view data-id="${esc(s.slug)}">view</button><button class="act danger" data-act=del data-id="${esc(s.slug)}">del</button>`;
        tb.appendChild(tr);
    }
}

async function loadCommands(query) {
    let items;
    if (query) {
        const matches = (await j('POST','/commands/search',{query,limit:20})).matches;
        const full = (await j('GET','/commands')).commands;
        const byName = Object.fromEntries(full.map(c => [c.slug, c]));
        items = matches.map(m => ({...byName[m.slug], d: m.distance.toFixed(3)}));
    } else {
        items = (await j('GET','/commands')).commands;
    }
    const tb = $('#commands-table tbody'); tb.innerHTML='';
    $('#commands-empty').hidden = items.length>0;
    for (const c of items) {
        const tr = document.createElement('tr');
        const uses = c.use_count>0 ? `<span class=tag>${c.use_count}</span>` : '<span class=dim>—</span>';
        const cmd_short = (c.command_line||'').split('\\n')[0].slice(0,80);
        tr.innerHTML = `<td class=mono>${esc(c.slug)}${c.d?' <span class=dim>d='+c.d+'</span>':''}<td><span class=tag>${esc(c.family||'')}</span><td>${uses}<td class=mono>${esc(cmd_short)}<td class=act><button class=act data-act=copy data-id="${esc(c.slug)}">copy</button><button class=act data-act=view data-id="${esc(c.slug)}">view</button><button class="act danger" data-act=del data-id="${esc(c.slug)}">del</button>`;
        tb.appendChild(tr);
    }
}

function fmtInt(n) {
    if (n === null || n === undefined) return '—';
    return n.toLocaleString('en-US');
}

// Compact suffix for the big lifetime tile.  10_500 -> "10.5K"; 1_250_000 ->
// "1.25M".  Keeps the headline readable when totals get into the millions.
function fmtCompact(n) {
    if (n === null || n === undefined) return '—';
    const abs = Math.abs(n);
    if (abs >= 1e9) return (n / 1e9).toFixed(2).replace(/\\.?0+$/,'') + 'B';
    if (abs >= 1e6) return (n / 1e6).toFixed(2).replace(/\\.?0+$/,'') + 'M';
    if (abs >= 1e3) return (n / 1e3).toFixed(1).replace(/\\.?0+$/,'') + 'K';
    return String(n);
}

async function loadTokens() {
    const s = await j('GET','/delegations/stats');
    const t = s.totals;
    $('#tok-lifetime').textContent = fmtCompact(t.lifetime_saved);
    $('#tok-lifetime-sub').textContent = fmtInt(t.lifetime_calls) + ' calls';
    $('#tok-24h').textContent = fmtCompact(t.last_24h_saved);
    $('#tok-24h-sub').textContent = fmtInt(t.last_24h_calls) + ' calls';
    $('#tok-7d').textContent = fmtCompact(t.last_7d_saved);
    $('#tok-7d-sub').textContent = fmtInt(t.last_7d_calls) + ' calls';
    $('#tok-30d').textContent = fmtCompact(t.last_30d_saved);
    $('#tok-30d-sub').textContent = fmtInt(t.last_30d_calls) + ' calls';

    // Sparkline.  Manual SVG bars are cheaper than a charting lib and
    // honour the no-CDN rule the rest of the GUI follows.  When the whole
    // 30-day window is zero we still render the axis so the tab doesn't
    // look broken.
    const days = s.daily_30d || [];
    const max = Math.max(1, ...days.map(d => d.saved));
    const W = 600, H = 60, gap = 2;
    const barW = Math.max(1, Math.floor((W - gap * (days.length - 1)) / days.length));
    const parts = [];
    let runningSaved = 0;
    let runningCalls = 0;
    days.forEach((d, i) => {
        runningSaved += d.saved;
        runningCalls += d.calls;
        const h = d.saved > 0 ? Math.max(2, Math.round((d.saved / max) * (H - 2))) : 0;
        const x = i * (barW + gap);
        const y = H - h;
        const cls = d.saved > 0 ? 'bar' : 'bar zero';
        const title = d.date + ' — ' + fmtInt(d.saved) + ' tokens, ' + fmtInt(d.calls) + ' calls';
        parts.push(`<rect class='${cls}' x='${x}' y='${y}' width='${barW}' height='${h || 1}'><title>${title}</title></rect>`);
    });
    parts.push(`<line class=axis x1='0' y1='${H - .5}' x2='${W}' y2='${H - .5}'/>`);
    $('#spark-svg').innerHTML = parts.join('');
    $('#spark-meta').textContent =
        fmtInt(runningSaved) + ' tokens / ' + fmtInt(runningCalls) +
        ' calls / window max ' + fmtInt(max) + ' tokens';

    // Per-delegate table.
    const dtb = $('#tokens-by-delegate tbody'); dtb.innerHTML = '';
    $('#tok-del-empty').hidden = (s.per_delegate || []).length > 0;
    for (const r of (s.per_delegate || [])) {
        const tr = document.createElement('tr');
        const rate = r.n_calls > 0 ? (r.success_rate * 100).toFixed(0) + '%' : '—';
        tr.innerHTML =
            `<td class=mono>${esc(r.name)}` +
            `<td class=num>${fmtInt(r.total_saved)}` +
            `<td class=num>${fmtInt(r.n_calls)}` +
            `<td class=num>${rate}`;
        dtb.appendChild(tr);
    }

    // Per-capability table.
    const ctb = $('#tokens-by-capability tbody'); ctb.innerHTML = '';
    $('#tok-cap-empty').hidden = (s.per_capability || []).length > 0;
    for (const r of (s.per_capability || [])) {
        const tr = document.createElement('tr');
        const rate = r.n_calls > 0 ? (r.success_rate * 100).toFixed(0) + '%' : '—';
        tr.innerHTML =
            `<td class=mono>${esc(r.name)}` +
            `<td class=num>${fmtInt(r.total_saved)}` +
            `<td class=num>${fmtInt(r.n_calls)}` +
            `<td class=num>${rate}`;
        ctb.appendChild(tr);
    }
}

function load(tab) {
    if (tab==='scripts')      loadScripts($('#scripts-q').value);
    else if (tab==='patterns') loadPatterns($('#patterns-q').value);
    else if (tab==='tech') loadTech($('#tech-q').value);
    else if (tab==='snippets') loadSnippets($('#snippets-q').value);
    else if (tab==='commands') loadCommands($('#commands-q').value);
    else if (tab==='stacks') loadStacks($('#stacks-q').value);
    else if (tab==='antipatterns') loadAP($('#ap-q').value);
    else if (tab==='delegates') loadDelegates();
    else if (tab==='tokens')  loadTokens();
    else if (tab==='vault')   loadVault();
    else if (tab==='audit')   loadAudit();
}

// Debounced search — typing fired a search+full-list fetch (each an Ollama embed
// round-trip + drvfs reindex) on EVERY keystroke; that was the "slow query".
$('#scripts-q').oninput = debounce(e => { scriptsPage=0; loadScripts(e.target.value); }, 220);
$('#patterns-q').oninput = debounce(e => loadPatterns(e.target.value), 220);
$('#tech-q').oninput     = debounce(e => loadTech(e.target.value), 220);
$('#snippets-q').oninput = debounce(e => loadSnippets(e.target.value), 220);
$('#commands-q').oninput = debounce(e => loadCommands(e.target.value), 220);
$('#stacks-q').oninput   = debounce(e => loadStacks(e.target.value), 220);
$('#ap-q').oninput       = debounce(e => loadAP(e.target.value), 220);

// Generic catalog row actions: view (modal), copy (body to clipboard), del.
const CATALOG = {
  patterns:{tbl:'#patterns-table',ep:'/design-patterns',reload:()=>loadPatterns($('#patterns-q').value),body:'example'},
  tech:{tbl:'#tech-table',ep:'/technologies',reload:()=>loadTech($('#tech-q').value),body:'limitations'},
  snippets:{tbl:'#snippets-table',ep:'/snippets',reload:()=>loadSnippets($('#snippets-q').value),body:'body'},
  commands:{tbl:'#commands-table',ep:'/commands',reload:()=>loadCommands($('#commands-q').value),body:'command_line'},
  stacks:{tbl:'#stacks-table',ep:'/stacks',reload:()=>loadStacks($('#stacks-q').value),body:'context'},
};
for(const [k,c] of Object.entries(CATALOG)){
  $(c.tbl+' tbody').onclick = async e => {
    const b=e.target.closest('button[data-act]'); if(!b) return;
    const slug=b.dataset.id, label=k.replace(/s$/,'')+' '+slug;
    if(b.dataset.act==='del'){ delItem(label, c.ep+'/'+encodeURIComponent(slug), k, c.reload); return; }
    const r=await j('GET',c.ep+'/'+encodeURIComponent(slug));
    const body=r[c.body];
    if(b.dataset.act==='copy'){ if(body) copyText(body); else toast('nothing to copy',1); }
    else showModal(label,{text:body||JSON.stringify(r,null,2),copyVal:body||''});
  };
}

j('GET','/healthz').then(h => $('#health').textContent = (h.ok?'ok':'down')+' · '+h.embed_model+' · vec '+h.sqlite_vec_version);
load('scripts');
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse, operation_id="index_gui")
def index() -> HTMLResponse:
    """Single-page explorer GUI for humans.  No build step, no CDN, no frameworks."""
    return HTMLResponse(_GUI_HTML)


# ---------------------------------------------------------------------------
# /healthz
# ---------------------------------------------------------------------------
@app.get("/healthz", operation_id="healthz")
def healthz() -> dict[str, Any]:
    with _conn() as c:
        try:
            (ver,) = c.execute("SELECT vec_version()").fetchone()
        except sqlite3.OperationalError as exc:
            return {
                "ok": False,
                "error": f"sqlite-vec not loadable: {exc}",
                "library_root": str(LIBRARY_ROOT),
            }
    return {
        "ok": True,
        "library_root": str(LIBRARY_ROOT),
        "scripts_dir_exists": SCRIPTS_DIR.is_dir(),
        "vault_exists": VAULT_PATH.is_file(),
        "db_path": str(DB_PATH),
        "sqlite_vec_version": ver,
        "embed_backend": "ollama" if OLLAMA_EMBED_URL else "sentence-transformers",
        "embed_model": (
            f"{OLLAMA_EMBED_MODEL}@{OLLAMA_EMBED_URL}"
            if OLLAMA_EMBED_URL
            else EMBED_MODEL_NAME
        ),
        "embed_model_loaded": (
            True if OLLAMA_EMBED_URL else _embed_model is not None
        ),
        "embed_dim": EMBED_DIM,
    }


# ---------------------------------------------------------------------------
# Script discovery
# ---------------------------------------------------------------------------
_FRONTMATTER_RE = re.compile(
    r"^#!.*?\n(?:#\s*=+\n)?(?P<body>(?:#.*\n)+?)(?:#\s*=+\n|\n)",
    re.DOTALL | re.MULTILINE,
)


def _parse_script_frontmatter(path: Path) -> dict[str, Any]:
    """Best-effort frontmatter parse for shell scripts.  See the convention
    documented in ``/path/to/rote/INDEX.md``."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {"error": f"unreadable: {exc}"}

    match = _FRONTMATTER_RE.match(text)
    header = match.group("body") if match else ""

    meta: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in header.splitlines():
        line = raw_line.lstrip("#").rstrip()
        if not line.strip():
            continue
        if current_key and (raw_line.startswith("#   ") or raw_line.startswith("#  -")):
            meta[current_key] = (meta[current_key] + "\n" + line.strip()).strip()
            continue
        if ":" in line:
            k, _, v = line.partition(":")
            k = k.strip().lower().replace(" ", "_").replace("-", "_")
            v = v.strip()
            meta[k] = v
            current_key = k
        else:
            meta.setdefault("raw_header", "")
            meta["raw_header"] = (meta["raw_header"] + "\n" + line.strip()).strip()
            current_key = None
    return meta


# Script file extensions we recognize.  Maps to the default environment tag
# the indexer applies when frontmatter doesn't say otherwise.  Cross-platform
# runtimes (python, node) get "cross-*" defaults; OS-specific scripts get
# explicit tags so /scripts/family/{f}?environment=<tag> can route correctly.
_SCRIPT_EXTENSIONS: dict[str, str] = {
    ".sh":   "posix-bash",
    ".bash": "posix-bash",
    ".zsh":  "posix-zsh",
    ".fish": "posix-fish",
    ".ps1":  "windows-pwsh",
    ".cmd":  "windows-cmd",
    ".bat":  "windows-cmd",
    ".py":   "cross-python",
    ".js":   "cross-node",
    ".mjs":  "cross-node",
    ".ts":   "cross-node",  # tsx-style; expects tsx or ts-node in PATH
    ".rb":   "cross-ruby",
}


def _default_environment_for_path(path: Path) -> str:
    return _SCRIPT_EXTENSIONS.get(path.suffix, "unknown")


def _sync_scripts() -> int:
    """Walk SCRIPTS_DIR, upsert into script_index, re-embed any whose mtime
    moved, and PRUNE rows whose on-disk path has disappeared (renames,
    deletes, repo relocations).  Returns the count of scripts (re-)indexed.
    Cheap to call from any list/search request because the embed step
    short-circuits on mtime match."""
    if not SCRIPTS_DIR.is_dir():
        return 0
    paths = [p for p in sorted(SCRIPTS_DIR.iterdir()) if p.suffix in _SCRIPT_EXTENSIONS]
    on_disk_set = {str(p) for p in paths}

    # Prune rows whose path no longer exists on disk.  Removes the stale
    # row from script_index AND its matching vec0 row so semantic search
    # doesn't keep returning a phantom.
    pruned_paths: list[str] = []
    with _conn() as c:
        stale = [
            (rowid, path)
            for rowid, path in c.execute("SELECT rowid, path FROM script_index")
            if path not in on_disk_set
        ]
        for rowid, path in stale:
            c.execute("DELETE FROM script_index WHERE rowid = ?", (rowid,))
            c.execute("DELETE FROM script_vec WHERE rowid = ?", (rowid,))
            pruned_paths.append(path)
    # Audit outside the prune transaction so we don't deadlock on the write lock.
    if pruned_paths:
        _audit("script.pruned", {"removed": pruned_paths})

    if not paths:
        return 0

    reindexed = 0
    with _conn() as c:
        for p in paths:
            mtime = int(p.stat().st_mtime)
            row = c.execute(
                "SELECT rowid, mtime_unix FROM script_index WHERE path = ?",
                (str(p),),
            ).fetchone()
            if row and row[1] == mtime:
                continue  # up-to-date

            fm = _parse_script_frontmatter(p)
            purpose = fm.get("purpose", "")
            when_to_use = fm.get("when_to_use", "") or fm.get("when_to_use__use", "")
            touches = fm.get("touches_secrets", "unknown") or "unknown"
            embed_text = f"{purpose}\n{when_to_use}".strip()

            if row:
                c.execute(
                    "UPDATE script_index SET mtime_unix=?, purpose=?, when_to_use=?, "
                    "touches_secrets=?, frontmatter_json=?, embed_text=? WHERE path=?",
                    (
                        mtime,
                        purpose,
                        when_to_use,
                        touches,
                        json.dumps(fm, sort_keys=True),
                        embed_text,
                        str(p),
                    ),
                )
                rowid = row[0]
            else:
                cur = c.execute(
                    "INSERT INTO script_index "
                    "(path, mtime_unix, purpose, when_to_use, touches_secrets, "
                    "frontmatter_json, embed_text) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(p),
                        mtime,
                        purpose,
                        when_to_use,
                        touches,
                        json.dumps(fm, sort_keys=True),
                        embed_text,
                    ),
                )
                rowid = cur.lastrowid

            # Refresh embedding.  Replace any prior row in the vec table.
            c.execute("DELETE FROM script_vec WHERE rowid = ?", (rowid,))
            if embed_text:
                c.execute(
                    "INSERT INTO script_vec (rowid, embedding) VALUES (?, ?)",
                    (rowid, _embed(embed_text)),
                )
            reindexed += 1
    return reindexed


def _script_stats(c: sqlite3.Connection, script_name: str) -> dict[str, Any]:
    """Aggregate run outcomes for one script.  Returns counters + derived
    success_rate + avg_duration_ms + last_run timestamps.  Cheap — single
    grouped query against the indexed log table."""
    row = c.execute(
        """
        SELECT
            COUNT(*)                                                  AS run_count,
            SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END)      AS success_count,
            SUM(CASE WHEN outcome = 'partial' THEN 1 ELSE 0 END)      AS partial_count,
            SUM(CASE WHEN outcome IN ('failure','timeout') THEN 1 ELSE 0 END) AS failure_count,
            AVG(duration_ms)                                          AS avg_duration_ms,
            MAX(ts_unix_ms)                                           AS last_run_ts,
            MAX(CASE WHEN outcome IN ('failure','timeout') THEN ts_unix_ms ELSE 0 END) AS last_failure_ts
        FROM script_run_log
        WHERE script_name = ?
        """,
        (script_name,),
    ).fetchone()
    run_count = row[0] or 0
    success_count = row[1] or 0
    partial_count = row[2] or 0
    failure_count = row[3] or 0
    # Score: success=1, partial=0.5, everything else=0.  Matches the delegate
    # stats heuristic so callers form one mental model.
    wins = success_count + 0.5 * partial_count
    return {
        "run_count": run_count,
        "success_count": success_count,
        "partial_count": partial_count,
        "failure_count": failure_count,
        "success_rate": wins / run_count if run_count else None,
        "avg_duration_ms": row[4],
        "last_run_unix_ms": row[5],
        "last_failure_unix_ms": row[6] or None,
    }


def _environment_of(path: Path, fm: dict[str, Any]) -> str:
    """Determine the runtime env for a script: explicit frontmatter wins,
    falls back to the extension-default."""
    explicit = (fm.get("environment") or "").strip()
    return explicit or _default_environment_for_path(path)


def _family_of(path: Path, fm: dict[str, Any]) -> str:
    """Family slug: explicit frontmatter wins, falls back to the file stem
    (so single-environment scripts get a sensible family identity for free)."""
    explicit = (fm.get("family") or "").strip()
    return explicit or path.stem


@app.get("/scripts", operation_id="list_scripts")
def list_scripts(
    include_stats: bool = True,
    environment: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> dict[str, Any]:
    """List every reusable script with its parsed frontmatter (+ per-script
    run stats by default).  Triggers a cheap mtime-based reindex so the
    response always reflects on-disk state.

    Args:
        include_stats: when true (default), include run_count / failure_count
                       / success_rate per script
        environment: if set, filter to scripts whose `environment` matches.
                     Common values: posix-bash, windows-pwsh, cross-python,
                     cross-node.  Pass "any" or leave blank to disable filter.
    """
    _sync_scripts()
    out = []
    env_filter = (environment or "").strip().lower()
    with _conn() as c:
        for row in c.execute(
            "SELECT path, mtime_unix, purpose, when_to_use, touches_secrets, "
            "frontmatter_json FROM script_index ORDER BY path"
        ):
            p = Path(row[0])
            fm = json.loads(row[5])
            env = _environment_of(p, fm)
            family = _family_of(p, fm)
            if env_filter and env_filter != "any" and env != env_filter:
                continue
            entry = {
                "name": p.name,
                "path": row[0],
                "size_bytes": p.stat().st_size if p.is_file() else 0,
                "mtime_unix": row[1],
                "purpose": row[2],
                "when_to_use": row[3],
                "touches_secrets": row[4],
                "environment": env,
                "family": family,
                "frontmatter": fm,
            }
            if include_stats:
                entry["stats"] = _script_stats(c, p.name)
            out.append(entry)
    total = len(out)
    if limit is not None:
        start = max(0, offset)
        out = out[start:start + max(0, limit)]
    return {"scripts": out, "count": len(out), "total": total, "offset": max(0, offset)}


@app.get("/scripts/family/{family}", operation_id="get_script_family")
def get_script_family(
    family: str,
    environment: str | None = None,
) -> dict[str, Any]:
    """Look up all variants of a logical script (same `family` slug)
    across runtime environments.  When `environment` is set, the response
    sorts the matching variant first and includes `best_match` (or null
    when no variant matches the requested env).

    Use this when you know the LOGICAL operation but not which variant to
    invoke from the current runtime.

    Args:
        family: the family slug (frontmatter family: field, or the file
                stem when no explicit family is declared)
        environment: prefer variants whose environment matches
    """
    _sync_scripts()
    env_pref = (environment or "").strip().lower()
    variants: list[dict[str, Any]] = []
    with _conn() as c:
        for row in c.execute(
            "SELECT path, mtime_unix, purpose, when_to_use, touches_secrets, "
            "frontmatter_json FROM script_index ORDER BY path"
        ):
            p = Path(row[0])
            fm = json.loads(row[5])
            fam = _family_of(p, fm)
            if fam != family:
                continue
            env = _environment_of(p, fm)
            entry = {
                "name": p.name, "path": row[0],
                "environment": env, "family": fam,
                "purpose": row[2], "when_to_use": row[3],
                "touches_secrets": row[4],
                "frontmatter": fm,
                "stats": _script_stats(c, p.name),
            }
            variants.append(entry)
    if not variants:
        raise HTTPException(404, f"no scripts in family: {family}")
    best_match = None
    if env_pref and env_pref != "any":
        # Prefer the explicit env match; else the first cross-* match; else None
        exact = [v for v in variants if v["environment"] == env_pref]
        if exact:
            best_match = exact[0]
        else:
            crossers = [v for v in variants if v["environment"].startswith("cross-")]
            if crossers:
                best_match = crossers[0]
        # Sort the response so the best-match is first
        if best_match:
            variants.remove(best_match)
            variants.insert(0, best_match)
    return {
        "family": family,
        "requested_environment": env_pref or None,
        "best_match": best_match,
        "variants": variants,
        "count": len(variants),
    }


@app.get("/scripts/{name}", operation_id="get_script")
def get_script(name: str) -> dict[str, Any]:
    _sync_scripts()
    p = SCRIPTS_DIR / name
    if not p.is_file():
        raise HTTPException(404, f"unknown script: {name}")
    with _conn() as c:
        row = c.execute(
            "SELECT path, mtime_unix, purpose, when_to_use, touches_secrets, "
            "frontmatter_json FROM script_index WHERE path = ?",
            (str(p),),
        ).fetchone()
        if not row:
            raise HTTPException(404, f"unindexed script: {name}")
        stats = _script_stats(c, p.name)
        recent_log = list(
            c.execute(
                "SELECT ts_unix_ms, outcome, exit_code, duration_ms, caller, "
                "args_preview, notes FROM script_run_log "
                "WHERE script_name = ? ORDER BY ts_unix_ms DESC LIMIT 25",
                (p.name,),
            )
        )
    fm = json.loads(row[5])
    return {
        "name": p.name,
        "path": row[0],
        "size_bytes": p.stat().st_size,
        "mtime_unix": row[1],
        "purpose": row[2],
        "when_to_use": row[3],
        "touches_secrets": row[4],
        "environment": _environment_of(p, fm),
        "family": _family_of(p, fm),
        "frontmatter": fm,
        "stats": stats,
        "recent_log": [
            {
                "ts_unix_ms": r[0], "outcome": r[1], "exit_code": r[2],
                "duration_ms": r[3], "caller": r[4],
                "args_preview": r[5], "notes": r[6],
            }
            for r in recent_log
        ],
    }


class ScriptRunLogCreate(BaseModel):
    outcome: str = Field(..., description="success | failure | partial | timeout")
    exit_code: int | None = None
    duration_ms: int | None = None
    caller: str = Field(default="", description="cli | mcp | direct | <other>")
    args_preview: str = Field(default="", max_length=500)
    notes: str = ""


@app.post("/scripts/{name}/runs", operation_id="log_script_run")
def log_script_run(name: str, req: ScriptRunLogCreate) -> dict[str, Any]:
    """Record one execution of a script.  Called automatically by `rote
    run` and the MCP `run_script` tool; callable manually for ad-hoc
    invocations Claude made outside those paths.  Aggregates feed
    /scripts/{name}.stats."""
    if req.outcome not in {"success", "failure", "partial", "timeout"}:
        raise HTTPException(400, f"unknown outcome: {req.outcome}")
    p = SCRIPTS_DIR / name
    if not p.is_file():
        raise HTTPException(404, f"unknown script: {name}")
    with _conn() as c:
        c.execute(
            "INSERT INTO script_run_log "
            "(script_name, ts_unix_ms, outcome, exit_code, duration_ms, "
            " caller, args_preview, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                name,
                int(time.time() * 1000),
                req.outcome,
                req.exit_code,
                req.duration_ms,
                req.caller,
                req.args_preview,
                req.notes,
            ),
        )
    _audit(
        "script.run",
        {
            "script": name,
            "outcome": req.outcome,
            "exit_code": req.exit_code,
            "duration_ms": req.duration_ms,
            "caller": req.caller,
        },
    )
    return {"script": name, "outcome": req.outcome, "action": "logged"}


@app.get("/scripts/{name}/runs", operation_id="list_script_runs")
def list_script_runs(name: str, limit: int = 50) -> dict[str, Any]:
    """List recent run-log entries for a script."""
    limit = max(1, min(500, limit))
    with _conn() as c:
        rows = list(
            c.execute(
                "SELECT ts_unix_ms, outcome, exit_code, duration_ms, caller, "
                "args_preview, notes FROM script_run_log "
                "WHERE script_name = ? ORDER BY ts_unix_ms DESC LIMIT ?",
                (name, limit),
            )
        )
    return {
        "script": name,
        "events": [
            {
                "ts_unix_ms": r[0], "outcome": r[1], "exit_code": r[2],
                "duration_ms": r[3], "caller": r[4],
                "args_preview": r[5], "notes": r[6],
            }
            for r in rows
        ],
        "count": len(rows),
    }


class ScriptSearchRequest(BaseModel):
    query: str = Field(..., description="Free-text description of what you want")
    limit: int = Field(default=5, ge=1, le=50)


@app.post("/scripts/search", operation_id="search_scripts")
def search_scripts(req: ScriptSearchRequest) -> dict[str, Any]:
    """Semantic similarity search over script frontmatter purpose +
    when-to-use.  Returns top-k by cosine distance (closer = better)."""
    _sync_scripts()
    q = _embed(req.query)
    with _conn() as c:
        rows = list(
            c.execute(
                """
                SELECT
                    script_index.path,
                    script_index.purpose,
                    script_index.when_to_use,
                    script_index.touches_secrets,
                    script_vec.distance
                FROM script_vec
                JOIN script_index ON script_index.rowid = script_vec.rowid
                WHERE script_vec.embedding MATCH ? AND k = ?
                ORDER BY script_vec.distance
                """,
                (q, req.limit),
            )
        )
    _audit("scripts.search", {"query_len": len(req.query), "limit": req.limit, "hits": len(rows)})
    return {
        "query": req.query,
        "matches": [
            {
                "name": Path(r[0]).name,
                "path": r[0],
                "purpose": r[1],
                "when_to_use": r[2],
                "touches_secrets": r[3],
                "distance": r[4],
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# Vault — secret-name discovery + inject.  NEVER returns bytes.
# ---------------------------------------------------------------------------
def _load_vault() -> dict[str, str]:
    if not VAULT_PATH.is_file():
        return {}
    try:
        with VAULT_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise HTTPException(500, "vault: top-level JSON must be an object")
        return {k: v for k, v in data.items() if isinstance(v, str)}
    except json.JSONDecodeError as exc:
        raise HTTPException(500, f"vault: malformed JSON: {exc}") from exc


@app.get("/vault/keys", operation_id="vault_keys")
def vault_keys() -> dict[str, Any]:
    v = _load_vault()
    keys = sorted(({"name": k, "bytes": len(val)} for k, val in v.items()), key=lambda x: x["name"])
    _audit("vault.list", {"count": len(keys)})
    return {"keys": keys, "vault_path": str(VAULT_PATH), "count": len(keys)}


class VaultHasRequest(BaseModel):
    keys: list[str]


@app.post("/vault/has", operation_id="vault_has")
def vault_has(req: VaultHasRequest) -> dict[str, Any]:
    v = _load_vault()
    out = {k: (k in v) for k in req.keys}
    _audit("vault.has", {"asked": req.keys, "found": [k for k, ok in out.items() if ok]})
    return {"exists": out}


_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class VaultInjectRequest(BaseModel):
    env_file: str = Field(..., description="Absolute path to the target .env file")
    keys: list[str]
    block_label: str = Field(
        default="rote:vault-inject",
        description=(
            "Idempotency anchor.  All injected vars are wrapped between "
            "``# >>> {label} >>>`` and ``# <<< {label} <<<`` markers; a prior "
            "block with the same label is replaced atomically."
        ),
    )


def _validate_env_path(p: str) -> Path:
    if ".." in p.split("/"):
        raise HTTPException(400, "env_file: '..' segments are not allowed")
    path = Path(p)
    if not path.is_absolute():
        raise HTTPException(400, "env_file: must be an absolute path")
    if path.name != ".env" and not path.name.endswith(".env"):
        raise HTTPException(400, f"env_file: name must be .env or *.env (got {path.name})")
    return path


def _replace_block(text: str, label: str, new_body: str) -> str:
    open_tag = f"# >>> {label} >>>"
    close_tag = f"# <<< {label} <<<"
    pat = re.compile(re.escape(open_tag) + r".*?" + re.escape(close_tag) + r"\n?", re.DOTALL)
    block = f"{open_tag}\n{new_body.rstrip()}\n{close_tag}\n"
    if pat.search(text):
        return pat.sub(block, text)
    sep = "" if text.endswith("\n") or not text else "\n"
    return text + sep + block


@app.post("/vault/inject", operation_id="vault_inject")
def vault_inject(req: VaultInjectRequest) -> dict[str, Any]:
    path = _validate_env_path(req.env_file)
    vault = _load_vault()

    wrote: list[dict[str, Any]] = []
    missing: list[str] = []
    body_lines: list[str] = []
    for key in req.keys:
        if not _ENV_KEY_RE.match(key):
            raise HTTPException(400, f"key: not a valid env-style identifier: {key}")
        if key not in vault:
            missing.append(key)
            continue
        val = vault[key]
        if "\n" in val:
            body_lines.append(f'{key}="{val}"')
        elif any(ch in val for ch in (" ", "\t", "#", '"', "'", "\\")):
            escaped = val.replace("\\", "\\\\").replace('"', '\\"')
            body_lines.append(f'{key}="{escaped}"')
        else:
            body_lines.append(f"{key}={val}")
        wrote.append({"name": key, "bytes": len(val)})

    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    updated = _replace_block(existing, req.block_label, "\n".join(body_lines))
    path.write_text(updated, encoding="utf-8")

    _audit(
        "vault.inject",
        {
            "env_file": str(path),
            "label": req.block_label,
            "wrote": [w["name"] for w in wrote],
            "wrote_bytes": [w["bytes"] for w in wrote],
            "missing": missing,
        },
    )
    return {
        "env_file": str(path),
        "block_label": req.block_label,
        "wrote": wrote,
        "missing": missing,
        "ok": not missing,
    }


class VaultImportEnvFileRequest(BaseModel):
    env_file: str = Field(..., description="Absolute path to a .env-style file the SERVER will read")
    overwrite: bool = Field(
        default=False,
        description=(
            "When False (default), keys already in the vault are left untouched "
            "and reported under `skipped`.  When True, the .env value replaces "
            "the existing vault value."
        ),
    )


def _parse_env_lines(text: str) -> list[tuple[str, str]]:
    """Lightweight .env parser — accepts KEY=VALUE per line, supports
    surrounding double or single quotes (and unescapes \\n / \\" inside
    double quotes), skips blank lines and `#`-prefixed comments.  Returns
    pairs in source order; later occurrences win on duplicate keys."""
    out: list[tuple[str, str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Strip a leading `export ` for Bash-compat .envs
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        eq = line.find("=")
        if eq < 0:
            continue
        key = line[:eq].strip()
        val = line[eq + 1 :]
        if not _ENV_KEY_RE.match(key):
            continue
        # Strip an inline `#` comment when the value isn't quoted
        if not (val.startswith('"') or val.startswith("'")):
            hash_pos = val.find(" #")
            if hash_pos >= 0:
                val = val[:hash_pos]
            val = val.strip()
        if val.startswith('"') and val.endswith('"') and len(val) >= 2:
            inner = val[1:-1]
            val = inner.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")
        elif val.startswith("'") and val.endswith("'") and len(val) >= 2:
            val = val[1:-1]
        out.append((key, val))
    return out


@app.post("/vault/import-env-file", operation_id="vault_import_env_file")
def vault_import_env_file(req: VaultImportEnvFileRequest) -> dict[str, Any]:
    """Read a .env-style file off disk SERVER-SIDE and merge its KEY=VALUE
    entries into the vault.  The value bytes never traverse the API
    response — the only data returned is per-key metadata (name + byte
    count + action).  Audit log records the names of keys imported
    (never values).

    Designed for "load deploy.env into the vault" workflows where the
    caller (Claude, an operator script, etc.) must not be exposed to the
    secret bytes."""
    path = _validate_env_path(req.env_file)
    if not path.is_file():
        raise HTTPException(404, f"env_file: not found on disk: {path}")
    raw = path.read_text(encoding="utf-8")
    parsed = _parse_env_lines(raw)
    if not parsed:
        raise HTTPException(400, f"env_file: no parseable KEY=VALUE lines found in {path}")

    VAULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    vault = _load_vault()
    added: list[dict[str, Any]] = []
    updated: list[dict[str, Any]] = []
    skipped: list[str] = []
    seen: set[str] = set()
    for key, val in parsed:
        if key in seen:
            # Later wins; pop earlier action records for the same key.
            added = [a for a in added if a["name"] != key]
            updated = [u for u in updated if u["name"] != key]
        seen.add(key)
        if key in vault:
            if not req.overwrite:
                skipped.append(key)
                continue
            vault[key] = val
            updated.append({"name": key, "bytes": len(val)})
        else:
            vault[key] = val
            added.append({"name": key, "bytes": len(val)})

    # Write atomically: write to a sibling temp file + rename so a crash
    # mid-write leaves the prior vault intact.
    tmp = VAULT_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(vault, indent=2, sort_keys=True), encoding="utf-8")
    try:
        _os.chmod(tmp, 0o600)
    except OSError:
        # drvfs / Windows-mounted FS ignores chmod — non-fatal.
        pass
    tmp.replace(VAULT_PATH)

    _audit(
        "vault.import_env_file",
        {
            "env_file": str(path),
            "added": [a["name"] for a in added],
            "updated": [u["name"] for u in updated],
            "skipped": skipped,
            "overwrite": req.overwrite,
        },
    )
    return {
        "env_file": str(path),
        "added": added,
        "updated": updated,
        "skipped": skipped,
        "total_in_vault": len(vault),
        "overwrite": req.overwrite,
    }


# ---------------------------------------------------------------------------
# Anti-patterns — relational CRUD + vector search.
# ---------------------------------------------------------------------------
class AntiPatternCreate(BaseModel):
    slug: str = Field(..., description="kebab-case unique slug")
    title: str
    symptom: str = Field(..., description="What it looks like in the wild")
    token_cost: str | None = Field(default=None)
    remedy: str = Field(..., description="The right pattern — what to do instead")


def _anti_pattern_embed_text(slug: str, title: str, symptom: str, remedy: str) -> str:
    return f"{title}\n{symptom}\n{remedy}".strip()


# ---------------------------------------------------------------------------
# Filesystem-backed anti-patterns: parse .md files under ANTI_PATTERNS_DIR with
# YAML frontmatter, upsert into the same anti_patterns table the POST endpoint
# uses.  Mirror of _sync_scripts() so future sessions can drop a markdown file
# and have it picked up automatically by list/search on next call.
# ---------------------------------------------------------------------------
_MD_FRONTMATTER_RE = re.compile(r"^---\s*\n(?P<body>.*?)\n---\s*\n(?P<rest>.*)$", re.DOTALL)


def _parse_md_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    """Parse the simple `key: value`-style YAML frontmatter we use in the
    seeded markdown.  Returns (meta_dict, body_after_frontmatter)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}, ""

    match = _MD_FRONTMATTER_RE.match(text)
    if not match:
        return {}, text

    meta: dict[str, Any] = {}
    for raw_line in match.group("body").splitlines():
        line = raw_line.rstrip()
        if not line.strip() or ":" not in line:
            continue
        k, _, v = line.partition(":")
        meta[k.strip().lower().replace(" ", "_").replace("-", "_")] = v.strip()
    return meta, match.group("rest")


def _extract_section(body: str, header: str) -> str:
    """Pull the text under an H1/H2/H3 heading.  Header argument is the bare
    heading text (e.g. ``"Symptom"``).  Matches headings that start with the
    given text — trailing qualifiers like ``"Remedy (deterministic)"`` count.
    Returns content up to the next heading of the same or higher level,
    trimmed."""
    pat = re.compile(rf"^#{{1,6}}\s+{re.escape(header)}\b.*$", re.MULTILINE | re.IGNORECASE)
    m = pat.search(body)
    if not m:
        return ""
    start = m.end()
    next_h = re.search(r"^#{1,6}\s+", body[start:], re.MULTILINE)
    end = start + next_h.start() if next_h else len(body)
    return body[start:end].strip()


def _sync_anti_patterns() -> int:
    """Walk ANTI_PATTERNS_DIR, upsert each `*.md` with valid frontmatter into
    the anti_patterns table.  Idempotent — uses slug as the dedupe key and only
    re-embeds when content changed.  Hit-count is NOT bumped by file
    reindexing (that would conflate "ran chronicle" with "filesystem
    refresh")."""
    if not ANTI_PATTERNS_DIR.is_dir():
        return 0

    paths = sorted(ANTI_PATTERNS_DIR.glob("*.md"))
    if not paths:
        return 0

    indexed = 0
    now = int(time.time())
    with _conn() as c:
        for p in paths:
            meta, body = _parse_md_frontmatter(p)
            slug = meta.get("slug") or p.stem
            title = meta.get("title") or slug
            token_cost = meta.get("token_cost") or None
            try:
                hit_count = int(meta.get("hit_count", "1"))
            except (TypeError, ValueError):
                hit_count = 1

            symptom = _extract_section(body, "Symptom") or _extract_section(body, "Symptoms")
            remedy = _extract_section(body, "Remedy") or _extract_section(body, "Remedies") or _extract_section(body, "Fix")
            if not symptom or not remedy:
                # Skip silently — file lacks the expected structure.  We don't
                # want to insert empty-embedding rows that pollute search.
                continue

            embed_text = _anti_pattern_embed_text(slug, title, symptom, remedy)
            row = c.execute(
                "SELECT id, rowid, embed_text, hit_count FROM anti_patterns WHERE slug = ?",
                (slug,),
            ).fetchone()
            if row and row[2] == embed_text:
                # Up-to-date.
                continue

            vec = _embed(embed_text)
            if row:
                # Preserve existing hit_count (never lower it) but allow the
                # markdown's hit_count to raise the floor.
                effective_hits = max(int(row[3]), hit_count)
                c.execute(
                    "UPDATE anti_patterns SET title=?, symptom=?, token_cost=?, "
                    "remedy=?, last_seen=?, hit_count=?, embed_text=? WHERE slug=?",
                    (title, symptom, token_cost, remedy, now, effective_hits, embed_text, slug),
                )
                rowid = row[1]
            else:
                ap_id = uuid.uuid4().hex
                cur = c.execute(
                    "INSERT INTO anti_patterns "
                    "(id, slug, title, symptom, token_cost, remedy, first_seen, last_seen, "
                    "hit_count, embed_text) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        ap_id, slug, title, symptom, token_cost, remedy,
                        now, now, hit_count, embed_text,
                    ),
                )
                rowid = cur.lastrowid

            c.execute("DELETE FROM anti_patterns_vec WHERE rowid = ?", (rowid,))
            c.execute(
                "INSERT INTO anti_patterns_vec (rowid, embedding) VALUES (?, ?)",
                (rowid, vec),
            )
            indexed += 1
    return indexed


@app.get("/anti-patterns", operation_id="list_anti_patterns")
def list_anti_patterns() -> dict[str, Any]:
    _sync_anti_patterns()
    with _conn() as c:
        rows = list(
            c.execute(
                "SELECT slug, title, symptom, token_cost, remedy, "
                "first_seen, last_seen, hit_count FROM anti_patterns "
                "ORDER BY hit_count DESC, last_seen DESC"
            )
        )
    return {
        "anti_patterns": [
            {
                "slug": r[0],
                "title": r[1],
                "symptom": r[2],
                "token_cost": r[3],
                "remedy": r[4],
                "first_seen_unix": r[5],
                "last_seen_unix": r[6],
                "hit_count": r[7],
            }
            for r in rows
        ],
        "count": len(rows),
    }


@app.post("/anti-patterns", operation_id="upsert_anti_pattern")
def upsert_anti_pattern(req: AntiPatternCreate) -> dict[str, Any]:
    """Insert or bump-hit-count an anti-pattern.  Slug is the dedupe key.
    Embedding is generated fresh on every upsert."""
    now = int(time.time())
    embed_text = _anti_pattern_embed_text(req.slug, req.title, req.symptom, req.remedy)
    vec = _embed(embed_text)
    with _conn() as c:
        existing = c.execute(
            "SELECT id, rowid FROM anti_patterns WHERE slug = ?", (req.slug,)
        ).fetchone()
        if existing:
            c.execute(
                "UPDATE anti_patterns SET title=?, symptom=?, token_cost=?, "
                "remedy=?, last_seen=?, hit_count=hit_count+1, embed_text=? "
                "WHERE slug=?",
                (req.title, req.symptom, req.token_cost, req.remedy, now, embed_text, req.slug),
            )
            ap_id, rowid = existing
            action = "bumped"
        else:
            ap_id = uuid.uuid4().hex
            cur = c.execute(
                "INSERT INTO anti_patterns "
                "(id, slug, title, symptom, token_cost, remedy, first_seen, last_seen, "
                "hit_count, embed_text) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
                (
                    ap_id,
                    req.slug,
                    req.title,
                    req.symptom,
                    req.token_cost,
                    req.remedy,
                    now,
                    now,
                    embed_text,
                ),
            )
            rowid = cur.lastrowid
            action = "created"
        c.execute("DELETE FROM anti_patterns_vec WHERE rowid = ?", (rowid,))
        c.execute(
            "INSERT INTO anti_patterns_vec (rowid, embedding) VALUES (?, ?)",
            (rowid, vec),
        )
    _audit("anti_pattern." + action, {"slug": req.slug})
    return {"id": ap_id, "slug": req.slug, "action": action}


class AntiPatternSearchRequest(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=50)


@app.post("/anti-patterns/search", operation_id="search_anti_patterns")
def search_anti_patterns(req: AntiPatternSearchRequest) -> dict[str, Any]:
    _sync_anti_patterns()
    q = _embed(req.query)
    with _conn() as c:
        rows = list(
            c.execute(
                """
                SELECT
                    anti_patterns.slug,
                    anti_patterns.title,
                    anti_patterns.symptom,
                    anti_patterns.remedy,
                    anti_patterns.hit_count,
                    anti_patterns_vec.distance
                FROM anti_patterns_vec
                JOIN anti_patterns ON anti_patterns.rowid = anti_patterns_vec.rowid
                WHERE anti_patterns_vec.embedding MATCH ? AND k = ?
                ORDER BY anti_patterns_vec.distance
                """,
                (q, req.limit),
            )
        )
    _audit("anti_pattern.search", {"query_len": len(req.query), "limit": req.limit, "hits": len(rows)})
    return {
        "query": req.query,
        "matches": [
            {
                "slug": r[0],
                "title": r[1],
                "symptom": r[2],
                "remedy": r[3],
                "hit_count": r[4],
                "distance": r[5],
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# Design patterns catalog — the GOOD-patterns counterpart to anti_patterns.
# Auto-indexed from markdown files under DESIGN_PATTERNS_DIR/<category>/<slug>.md
# (or directly under DESIGN_PATTERNS_DIR/<slug>.md with category in frontmatter).
# ---------------------------------------------------------------------------
def _design_pattern_embed_text(name: str, intent: str, when_to_use: str, structure: str) -> str:
    """Embedding text for semantic search.  Indexes name + intent + when-to-
    use + structure so queries like 'how to compose payment methods' or
    'safe retries across remote calls' land on the right pattern."""
    return f"{name}\n{intent}\n{when_to_use}\n{structure}".strip()


def _sync_design_patterns() -> int:
    """Walk DESIGN_PATTERNS_DIR (recursively) and upsert each *.md file into
    the design_patterns table.  Idempotent: only re-embeds when the parsed
    content actually changed.  Use-count is preserved across re-syncs."""
    if not DESIGN_PATTERNS_DIR.is_dir():
        return 0

    paths = sorted(DESIGN_PATTERNS_DIR.glob("**/*.md"))
    if not paths:
        return 0

    indexed = 0
    now = int(time.time())
    with _conn() as c:
        for p in paths:
            meta, body = _parse_md_frontmatter(p)
            slug = meta.get("slug") or p.stem
            name = meta.get("name") or slug.replace("-", " ").title()
            category = (
                meta.get("category")
                or (p.parent.name if p.parent != DESIGN_PATTERNS_DIR else "uncategorized")
            )
            intent = meta.get("intent") or ""
            references_links = meta.get("references") or meta.get("references_links") or ""

            when_to_use = _extract_section(body, "When to use") or _extract_section(body, "When")
            when_not_to_use = _extract_section(body, "When NOT to use") or _extract_section(body, "When NOT")
            structure = _extract_section(body, "Structure") or _extract_section(body, "Shape")
            example_code = _extract_section(body, "Example") or _extract_section(body, "Example code")
            relationships = _extract_section(body, "Relationships") or _extract_section(body, "Related")

            # Need at least a name + intent + when_to_use to be useful.
            if not intent or not when_to_use:
                continue

            embed_text = _design_pattern_embed_text(name, intent, when_to_use, structure)
            row = c.execute(
                "SELECT id, rowid, embed_text, use_count FROM design_patterns WHERE slug = ?",
                (slug,),
            ).fetchone()
            if row and row[2] == embed_text:
                continue  # up-to-date

            # Embed lookup is best-effort: when the local embed backend is
            # unavailable (Ollama down + sentence-transformers torch broken)
            # we still upsert the row WITHOUT a vector so list/show return
            # the entry.  Vector search will skip these rows until the
            # backend comes back; a subsequent sync re-attempts the embed.
            try:
                vec: bytes | None = _embed(embed_text)
            except Exception as exc:  # noqa: BLE001
                print(f"[sync.design_patterns] embed failed for {slug}: {exc}", flush=True)
                vec = None
            if row:
                c.execute(
                    "UPDATE design_patterns SET name=?, category=?, intent=?, when_to_use=?, "
                    "when_not_to_use=?, structure=?, example_code=?, relationships=?, "
                    "references_links=?, last_seen=?, embed_text=? WHERE slug=?",
                    (
                        name, category, intent, when_to_use, when_not_to_use,
                        structure, example_code, relationships, references_links,
                        now, embed_text, slug,
                    ),
                )
                rowid = row[1]
            else:
                dp_id = uuid.uuid4().hex
                cur = c.execute(
                    "INSERT INTO design_patterns "
                    "(id, slug, name, category, intent, when_to_use, when_not_to_use, "
                    " structure, example_code, relationships, references_links, "
                    " first_seen, last_seen, use_count, embed_text) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)",
                    (
                        dp_id, slug, name, category, intent, when_to_use,
                        when_not_to_use, structure, example_code, relationships,
                        references_links, now, now, embed_text,
                    ),
                )
                rowid = cur.lastrowid

            # Only touch the vec table when we actually have a vector.
            # When the embed backend was down (vec is None), skip the
            # vec insert so the relational row exists and list/show work;
            # next sync attempt retries the embed and seeds the vec row.
            if vec is not None:
                c.execute("DELETE FROM design_patterns_vec WHERE rowid = ?", (rowid,))
                c.execute(
                    "INSERT INTO design_patterns_vec (rowid, embedding) VALUES (?, ?)",
                    (rowid, vec),
                )
            indexed += 1
    return indexed


@app.get("/design-patterns", operation_id="list_design_patterns")
def list_design_patterns(category: str | None = None) -> dict[str, Any]:
    """List all catalogued design patterns.  Filter by ?category=<cat>.
    Categories used today: classical, architectural, resilience, offline,
    ai.  Add new categories just by dropping markdown files in a new
    subdirectory of design-patterns/."""
    _sync_design_patterns()
    sql = (
        "SELECT slug, name, category, intent, when_to_use, when_not_to_use, "
        "structure, example_code, relationships, references_links, "
        "first_seen, last_seen, use_count FROM design_patterns"
    )
    params: list[Any] = []
    if category:
        sql += " WHERE category = ?"
        params.append(category)
    sql += " ORDER BY category, name"
    with _conn() as c:
        rows = list(c.execute(sql, params))
    return {
        "design_patterns": [
            {
                "slug": r[0], "name": r[1], "category": r[2], "intent": r[3],
                "when_to_use": r[4], "when_not_to_use": r[5],
                "structure": r[6], "example_code": r[7],
                "relationships": r[8], "references": r[9],
                "first_seen_unix": r[10], "last_seen_unix": r[11],
                "use_count": r[12],
            }
            for r in rows
        ],
        "count": len(rows),
    }


@app.get("/design-patterns/{slug}", operation_id="get_design_pattern")
def get_design_pattern(slug: str) -> dict[str, Any]:
    _sync_design_patterns()
    with _conn() as c:
        row = c.execute(
            "SELECT slug, name, category, intent, when_to_use, when_not_to_use, "
            "structure, example_code, relationships, references_links, "
            "first_seen, last_seen, use_count FROM design_patterns WHERE slug = ?",
            (slug,),
        ).fetchone()
    if not row:
        raise HTTPException(404, f"unknown design pattern: {slug}")
    return {
        "slug": row[0], "name": row[1], "category": row[2], "intent": row[3],
        "when_to_use": row[4], "when_not_to_use": row[5],
        "structure": row[6], "example_code": row[7],
        "relationships": row[8], "references": row[9],
        "first_seen_unix": row[10], "last_seen_unix": row[11],
        "use_count": row[12],
    }


class DesignPatternSearchRequest(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=50)
    category: str | None = None


@app.post("/design-patterns/search", operation_id="search_design_patterns")
def search_design_patterns(req: DesignPatternSearchRequest) -> dict[str, Any]:
    """Semantic similarity search across pattern name + intent + when-to-use
    + structure.  Use BEFORE designing a new class hierarchy, service, or
    resilience layer — return what's known to work first, write fresh
    second."""
    _sync_design_patterns()
    q = _embed(req.query)
    with _conn() as c:
        if req.category:
            rows = list(c.execute(
                """
                SELECT
                    design_patterns.slug, design_patterns.name,
                    design_patterns.category, design_patterns.intent,
                    design_patterns.when_to_use, design_patterns.use_count,
                    design_patterns_vec.distance
                FROM design_patterns_vec
                JOIN design_patterns ON design_patterns.rowid = design_patterns_vec.rowid
                WHERE design_patterns_vec.embedding MATCH ? AND k = ?
                  AND design_patterns.category = ?
                ORDER BY design_patterns_vec.distance
                """,
                (q, req.limit, req.category),
            ))
        else:
            rows = list(c.execute(
                """
                SELECT
                    design_patterns.slug, design_patterns.name,
                    design_patterns.category, design_patterns.intent,
                    design_patterns.when_to_use, design_patterns.use_count,
                    design_patterns_vec.distance
                FROM design_patterns_vec
                JOIN design_patterns ON design_patterns.rowid = design_patterns_vec.rowid
                WHERE design_patterns_vec.embedding MATCH ? AND k = ?
                ORDER BY design_patterns_vec.distance
                """,
                (q, req.limit),
            ))
    _audit("design_pattern.search", {
        "query_len": len(req.query), "limit": req.limit,
        "category": req.category, "hits": len(rows),
    })
    return {
        "query": req.query,
        "category": req.category,
        "matches": [
            {
                "slug": r[0], "name": r[1], "category": r[2],
                "intent": r[3], "when_to_use": r[4],
                "use_count": r[5], "distance": r[6],
            }
            for r in rows
        ],
    }


@app.post("/design-patterns/{slug}/use", operation_id="log_design_pattern_use")
def log_design_pattern_use(slug: str, notes: str = "") -> dict[str, Any]:
    """Bump use_count on a pattern — call this when you actually reach for
    a pattern in code (not just look it up).  Lets us track which patterns
    are load-bearing vs which are just documented."""
    with _conn() as c:
        row = c.execute("SELECT id FROM design_patterns WHERE slug = ?", (slug,)).fetchone()
        if not row:
            raise HTTPException(404, f"unknown design pattern: {slug}")
        c.execute(
            "UPDATE design_patterns SET use_count = use_count + 1, last_seen = ? "
            "WHERE slug = ?",
            (int(time.time()), slug),
        )
    _audit("design_pattern.use", {"slug": slug, "notes": notes[:200]})
    return {"slug": slug, "action": "use_count_bumped"}


# ---------------------------------------------------------------------------
# Technologies catalog — concrete tools that implement design patterns.
# Each entry says what pattern(s) it implements, when to use, when NOT
# (offline-incompatibility, cloud-lock, etc.), and what to use instead.
# ---------------------------------------------------------------------------
def _tech_embed_text(name: str, category: str, when_to_use: str, limitations: str) -> str:
    return f"{name} ({category})\n{when_to_use}\nlimitations: {limitations}".strip()


def _sync_technologies() -> int:
    if not TECHNOLOGIES_DIR.is_dir():
        return 0
    paths = sorted(TECHNOLOGIES_DIR.glob("**/*.md"))
    if not paths:
        return 0
    indexed = 0
    now = int(time.time())
    with _conn() as c:
        for p in paths:
            meta, body = _parse_md_frontmatter(p)
            slug = meta.get("slug") or p.stem
            name = meta.get("name") or slug.replace("-", " ")
            category = (
                meta.get("category")
                or (p.parent.name if p.parent != TECHNOLOGIES_DIR else "uncategorized")
            )
            tags = meta.get("tags") or ""
            implements_patterns = meta.get("implements_patterns") or meta.get("implements") or ""
            references_links = meta.get("references") or ""

            when_to_use = _extract_section(body, "When to use") or _extract_section(body, "When")
            when_not_to_use = _extract_section(body, "When NOT to use") or _extract_section(body, "When NOT")
            limitations = _extract_section(body, "Limitations")
            cost_notes = _extract_section(body, "Cost") or _extract_section(body, "Cost notes")
            alternatives = _extract_section(body, "Alternatives")

            if not when_to_use and not limitations:
                continue

            embed_text = _tech_embed_text(name, category, when_to_use, limitations)
            row = c.execute(
                "SELECT id, rowid, embed_text FROM technologies WHERE slug = ?",
                (slug,),
            ).fetchone()
            if row and row[2] == embed_text:
                continue

            vec = _embed(embed_text)
            if row:
                c.execute(
                    "UPDATE technologies SET name=?, category=?, implements_patterns=?, "
                    "when_to_use=?, when_not_to_use=?, limitations=?, cost_notes=?, "
                    "alternatives=?, tags=?, references_links=?, last_seen=?, embed_text=? "
                    "WHERE slug=?",
                    (
                        name, category, implements_patterns, when_to_use, when_not_to_use,
                        limitations, cost_notes, alternatives, tags, references_links,
                        now, embed_text, slug,
                    ),
                )
                rowid = row[1]
            else:
                t_id = uuid.uuid4().hex
                cur = c.execute(
                    "INSERT INTO technologies "
                    "(id, slug, name, category, implements_patterns, when_to_use, when_not_to_use, "
                    " limitations, cost_notes, alternatives, tags, references_links, "
                    " first_seen, last_seen, use_count, embed_text) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)",
                    (
                        t_id, slug, name, category, implements_patterns, when_to_use,
                        when_not_to_use, limitations, cost_notes, alternatives, tags,
                        references_links, now, now, embed_text,
                    ),
                )
                rowid = cur.lastrowid

            c.execute("DELETE FROM technologies_vec WHERE rowid = ?", (rowid,))
            c.execute(
                "INSERT INTO technologies_vec (rowid, embedding) VALUES (?, ?)",
                (rowid, vec),
            )
            indexed += 1
    return indexed


@app.get("/technologies", operation_id="list_technologies")
def list_technologies(category: str | None = None, tag: str | None = None) -> dict[str, Any]:
    """List catalogued technologies, optionally filtered by category or tag.
    Common tags: offline-capable, self-hosted, cloud-only, vendor-locked,
    open-source."""
    _sync_technologies()
    sql = (
        "SELECT slug, name, category, implements_patterns, when_to_use, when_not_to_use, "
        "limitations, cost_notes, alternatives, tags, references_links, "
        "first_seen, last_seen, use_count FROM technologies"
    )
    params: list[Any] = []
    if category:
        sql += " WHERE category = ?"
        params.append(category)
    sql += " ORDER BY category, name"
    with _conn() as c:
        rows = list(c.execute(sql, params))
    items = [
        {
            "slug": r[0], "name": r[1], "category": r[2],
            "implements_patterns": r[3], "when_to_use": r[4],
            "when_not_to_use": r[5], "limitations": r[6],
            "cost_notes": r[7], "alternatives": r[8],
            "tags": r[9], "references": r[10],
            "first_seen_unix": r[11], "last_seen_unix": r[12],
            "use_count": r[13],
        }
        for r in rows
    ]
    if tag:
        items = [t for t in items if tag in (t["tags"] or "")]
    return {"technologies": items, "count": len(items)}


@app.get("/technologies/{slug}", operation_id="get_technology")
def get_technology(slug: str) -> dict[str, Any]:
    _sync_technologies()
    with _conn() as c:
        row = c.execute(
            "SELECT slug, name, category, implements_patterns, when_to_use, when_not_to_use, "
            "limitations, cost_notes, alternatives, tags, references_links, "
            "first_seen, last_seen, use_count FROM technologies WHERE slug = ?",
            (slug,),
        ).fetchone()
    if not row:
        raise HTTPException(404, f"unknown technology: {slug}")
    return {
        "slug": row[0], "name": row[1], "category": row[2],
        "implements_patterns": row[3], "when_to_use": row[4],
        "when_not_to_use": row[5], "limitations": row[6],
        "cost_notes": row[7], "alternatives": row[8],
        "tags": row[9], "references": row[10],
        "first_seen_unix": row[11], "last_seen_unix": row[12],
        "use_count": row[13],
    }


class TechnologySearchRequest(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=50)
    category: str | None = None


@app.post("/technologies/search", operation_id="search_technologies")
def search_technologies(req: TechnologySearchRequest) -> dict[str, Any]:
    """Semantic search across technology name + category + when-to-use +
    limitations.  Use to answer 'what tech implements this pattern, given
    my constraints?'"""
    _sync_technologies()
    q = _embed(req.query)
    with _conn() as c:
        if req.category:
            rows = list(c.execute(
                """
                SELECT technologies.slug, technologies.name, technologies.category,
                       technologies.when_to_use, technologies.limitations,
                       technologies.tags, technologies_vec.distance
                FROM technologies_vec
                JOIN technologies ON technologies.rowid = technologies_vec.rowid
                WHERE technologies_vec.embedding MATCH ? AND k = ?
                  AND technologies.category = ?
                ORDER BY technologies_vec.distance
                """,
                (q, req.limit, req.category),
            ))
        else:
            rows = list(c.execute(
                """
                SELECT technologies.slug, technologies.name, technologies.category,
                       technologies.when_to_use, technologies.limitations,
                       technologies.tags, technologies_vec.distance
                FROM technologies_vec
                JOIN technologies ON technologies.rowid = technologies_vec.rowid
                WHERE technologies_vec.embedding MATCH ? AND k = ?
                ORDER BY technologies_vec.distance
                """,
                (q, req.limit),
            ))
    _audit("technology.search", {"query_len": len(req.query), "limit": req.limit, "hits": len(rows)})
    return {
        "query": req.query, "category": req.category,
        "matches": [
            {
                "slug": r[0], "name": r[1], "category": r[2],
                "when_to_use": r[3], "limitations": r[4],
                "tags": r[5], "distance": r[6],
            }
            for r in rows
        ],
    }


@app.post("/technologies/{slug}/use", operation_id="log_technology_use")
def log_technology_use(slug: str, notes: str = "") -> dict[str, Any]:
    """Bump use_count when this tech is selected for a real implementation."""
    with _conn() as c:
        row = c.execute("SELECT id FROM technologies WHERE slug = ?", (slug,)).fetchone()
        if not row:
            raise HTTPException(404, f"unknown technology: {slug}")
        c.execute(
            "UPDATE technologies SET use_count = use_count + 1, last_seen = ? WHERE slug = ?",
            (int(time.time()), slug),
        )
    _audit("technology.use", {"slug": slug, "notes": notes[:200]})
    return {"slug": slug, "action": "use_count_bumped"}


# ---------------------------------------------------------------------------
# Snippets — parameterized code templates with ${PLACEHOLDER} substitution.
# Indexed from snippets/<language>/<slug>.md.
# ---------------------------------------------------------------------------
_CODE_FENCE_RE = re.compile(r"```[a-zA-Z0-9_+-]*\n(.*?)\n```", re.DOTALL)


def _extract_first_code_block(text: str) -> str:
    """Pull the first fenced code block out of a markdown section.  Returns
    the inner code without the fence lines, or the raw text if no fence."""
    m = _CODE_FENCE_RE.search(text)
    return m.group(1).strip() if m else text.strip()


def _parse_placeholders_section(text: str) -> list[dict[str, str]]:
    """Parse the # Placeholders section.  Each bullet of the form
    `- NAME: description (example: value)` becomes one placeholder dict."""
    out: list[dict[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("-"):
            continue
        body = line[1:].strip()
        if ":" not in body:
            continue
        name, _, rest = body.partition(":")
        name = name.strip()
        rest = rest.strip()
        example = ""
        # Pull (example: ...) suffix when present.
        ex_match = re.search(r"\(example:\s*([^)]+)\)", rest, re.IGNORECASE)
        if ex_match:
            example = ex_match.group(1).strip()
            rest = re.sub(r"\(example:[^)]+\)", "", rest, flags=re.IGNORECASE).strip()
        out.append({"name": name, "description": rest, "example": example})
    return out


def _sync_snippets() -> int:
    if not SNIPPETS_DIR.is_dir():
        return 0
    paths = sorted(SNIPPETS_DIR.glob("**/*.md"))
    if not paths:
        return 0
    indexed = 0
    now = int(time.time())
    with _conn() as c:
        for p in paths:
            meta, body = _parse_md_frontmatter(p)
            slug = meta.get("slug") or p.stem
            name = meta.get("name") or slug.replace("-", " ")
            language = meta.get("language") or (
                p.parent.name if p.parent != SNIPPETS_DIR else "unknown"
            )
            applies_patterns = meta.get("applies_patterns") or ""
            applies_technologies = meta.get("applies_technologies") or ""
            references_links = meta.get("references") or ""

            snippet_section = _extract_section(body, "Snippet") or _extract_section(body, "Code")
            snippet_body = _extract_first_code_block(snippet_section) if snippet_section else ""
            placeholders_section = _extract_section(body, "Placeholders")
            placeholders = _parse_placeholders_section(placeholders_section) if placeholders_section else []
            when_to_use = _extract_section(body, "When to use") or _extract_section(body, "When")
            when_not_to_use = _extract_section(body, "When NOT to use") or _extract_section(body, "When NOT")
            example_expansion = _extract_section(body, "Example expansion") or _extract_section(body, "Example")

            if not snippet_body:
                continue  # nothing to template, skip

            embed_text = f"{name}\n{language}\n{when_to_use}".strip()
            row = c.execute(
                "SELECT id, rowid, embed_text FROM snippets WHERE slug = ?",
                (slug,),
            ).fetchone()
            if row and row[2] == embed_text:
                continue

            vec = _embed(embed_text)
            placeholders_json = json.dumps(placeholders, sort_keys=True)
            if row:
                c.execute(
                    "UPDATE snippets SET name=?, language=?, applies_patterns=?, "
                    "applies_technologies=?, placeholders_json=?, body=?, "
                    "when_to_use=?, when_not_to_use=?, example_expansion=?, "
                    "references_links=?, last_seen=?, embed_text=? WHERE slug=?",
                    (
                        name, language, applies_patterns, applies_technologies,
                        placeholders_json, snippet_body, when_to_use,
                        when_not_to_use, example_expansion, references_links,
                        now, embed_text, slug,
                    ),
                )
                rowid = row[1]
            else:
                sn_id = uuid.uuid4().hex
                cur = c.execute(
                    "INSERT INTO snippets "
                    "(id, slug, name, language, applies_patterns, applies_technologies, "
                    " placeholders_json, body, when_to_use, when_not_to_use, "
                    " example_expansion, references_links, first_seen, last_seen, "
                    " use_count, embed_text) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)",
                    (
                        sn_id, slug, name, language, applies_patterns,
                        applies_technologies, placeholders_json, snippet_body,
                        when_to_use, when_not_to_use, example_expansion,
                        references_links, now, now, embed_text,
                    ),
                )
                rowid = cur.lastrowid

            c.execute("DELETE FROM snippets_vec WHERE rowid = ?", (rowid,))
            c.execute(
                "INSERT INTO snippets_vec (rowid, embedding) VALUES (?, ?)",
                (rowid, vec),
            )
            indexed += 1
    return indexed


@app.get("/snippets", operation_id="list_snippets")
def list_snippets(language: str | None = None) -> dict[str, Any]:
    """List parameterized code templates.  Filter by ?language=<tag>
    (python, csharp, typescript, bash, sql, etc.)."""
    _sync_snippets()
    sql = (
        "SELECT slug, name, language, applies_patterns, applies_technologies, "
        "placeholders_json, body, when_to_use, when_not_to_use, "
        "example_expansion, references_links, first_seen, last_seen, use_count "
        "FROM snippets"
    )
    params: list[Any] = []
    if language:
        sql += " WHERE language = ?"
        params.append(language)
    sql += " ORDER BY language, name"
    with _conn() as c:
        rows = list(c.execute(sql, params))
    return {
        "snippets": [
            {
                "slug": r[0], "name": r[1], "language": r[2],
                "applies_patterns": r[3], "applies_technologies": r[4],
                "placeholders": json.loads(r[5]),
                "body": r[6], "when_to_use": r[7], "when_not_to_use": r[8],
                "example_expansion": r[9], "references": r[10],
                "first_seen_unix": r[11], "last_seen_unix": r[12],
                "use_count": r[13],
            }
            for r in rows
        ],
        "count": len(rows),
    }


@app.get("/snippets/{slug}", operation_id="get_snippet")
def get_snippet(slug: str) -> dict[str, Any]:
    _sync_snippets()
    with _conn() as c:
        row = c.execute(
            "SELECT slug, name, language, applies_patterns, applies_technologies, "
            "placeholders_json, body, when_to_use, when_not_to_use, "
            "example_expansion, references_links, first_seen, last_seen, use_count "
            "FROM snippets WHERE slug = ?",
            (slug,),
        ).fetchone()
    if not row:
        raise HTTPException(404, f"unknown snippet: {slug}")
    return {
        "slug": row[0], "name": row[1], "language": row[2],
        "applies_patterns": row[3], "applies_technologies": row[4],
        "placeholders": json.loads(row[5]),
        "body": row[6], "when_to_use": row[7], "when_not_to_use": row[8],
        "example_expansion": row[9], "references": row[10],
        "first_seen_unix": row[11], "last_seen_unix": row[12],
        "use_count": row[13],
    }


class SnippetSearchRequest(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=50)
    language: str | None = None


@app.post("/snippets/search", operation_id="search_snippets")
def search_snippets(req: SnippetSearchRequest) -> dict[str, Any]:
    """Semantic search across snippet name + language + when-to-use."""
    _sync_snippets()
    q = _embed(req.query)
    with _conn() as c:
        if req.language:
            rows = list(c.execute(
                """
                SELECT snippets.slug, snippets.name, snippets.language,
                       snippets.when_to_use, snippets.use_count,
                       snippets_vec.distance
                FROM snippets_vec
                JOIN snippets ON snippets.rowid = snippets_vec.rowid
                WHERE snippets_vec.embedding MATCH ? AND k = ?
                  AND snippets.language = ?
                ORDER BY snippets_vec.distance
                """,
                (q, req.limit, req.language),
            ))
        else:
            rows = list(c.execute(
                """
                SELECT snippets.slug, snippets.name, snippets.language,
                       snippets.when_to_use, snippets.use_count,
                       snippets_vec.distance
                FROM snippets_vec
                JOIN snippets ON snippets.rowid = snippets_vec.rowid
                WHERE snippets_vec.embedding MATCH ? AND k = ?
                ORDER BY snippets_vec.distance
                """,
                (q, req.limit),
            ))
    return {
        "query": req.query, "language": req.language,
        "matches": [
            {
                "slug": r[0], "name": r[1], "language": r[2],
                "when_to_use": r[3], "use_count": r[4], "distance": r[5],
            }
            for r in rows
        ],
    }


class SnippetExpandRequest(BaseModel):
    values: dict[str, str] = Field(default_factory=dict, description="Map of placeholder NAME -> substituted value")


@app.post("/snippets/{slug}/expand", operation_id="expand_snippet")
def expand_snippet(slug: str, req: SnippetExpandRequest) -> dict[str, Any]:
    """Render a snippet with placeholder substitution.  Replaces every
    ${NAME} token in the body with the matching value.  Returns the rendered
    code + list of any placeholders that were left unfilled."""
    with _conn() as c:
        row = c.execute(
            "SELECT body, placeholders_json FROM snippets WHERE slug = ?", (slug,)
        ).fetchone()
    if not row:
        raise HTTPException(404, f"unknown snippet: {slug}")
    body = row[0]
    declared = json.loads(row[1])
    declared_names = {p["name"] for p in declared}

    rendered = body
    used: list[str] = []
    for name, value in req.values.items():
        token = "${" + name + "}"
        if token in rendered:
            rendered = rendered.replace(token, value)
            used.append(name)

    # Find any remaining ${X} tokens — these are the unfilled placeholders.
    remaining = sorted(set(re.findall(r"\$\{([A-Z_][A-Z0-9_]*)\}", rendered)))
    unknown_names = sorted(set(req.values.keys()) - declared_names) if declared_names else []
    return {
        "slug": slug,
        "rendered": rendered,
        "used_placeholders": used,
        "remaining_placeholders": remaining,
        "unknown_placeholders": unknown_names,
    }


@app.post("/snippets/{slug}/use", operation_id="log_snippet_use")
def log_snippet_use(slug: str, notes: str = "") -> dict[str, Any]:
    """Bump use_count when you actually applied this snippet in real code."""
    with _conn() as c:
        row = c.execute("SELECT id FROM snippets WHERE slug = ?", (slug,)).fetchone()
        if not row:
            raise HTTPException(404, f"unknown snippet: {slug}")
        c.execute(
            "UPDATE snippets SET use_count = use_count + 1, last_seen = ? WHERE slug = ?",
            (int(time.time()), slug),
        )
    _audit("snippet.use", {"slug": slug, "notes": notes[:200]})
    return {"slug": slug, "action": "use_count_bumped"}


# ---------------------------------------------------------------------------
# Stacks — witness statements: technology combinations we've tried, what
# worked, what didn't, when to reuse, when to avoid.
# ---------------------------------------------------------------------------
def _sync_stacks() -> int:
    if not STACKS_DIR.is_dir():
        return 0
    paths = sorted(STACKS_DIR.glob("**/*.md"))
    if not paths:
        return 0
    indexed = 0
    now = int(time.time())
    with _conn() as c:
        for p in paths:
            meta, body = _parse_md_frontmatter(p)
            slug = meta.get("slug") or p.stem
            name = meta.get("name") or slug.replace("-", " ")
            technologies = meta.get("technologies") or ""
            patterns = meta.get("patterns") or ""
            context = meta.get("context") or ""
            outcome = (meta.get("outcome") or "mixed").lower()
            if outcome not in {"success", "partial", "failure", "mixed"}:
                outcome = "mixed"
            references_links = meta.get("references") or ""

            what_worked = _extract_section(body, "What worked") or _extract_section(body, "Worked")
            what_didnt = _extract_section(body, "What didn") or _extract_section(body, "What didn't") or _extract_section(body, "Didn't work")
            when_to_reuse = _extract_section(body, "When to reuse") or _extract_section(body, "Reuse")
            when_to_avoid = _extract_section(body, "When to avoid") or _extract_section(body, "Avoid")

            embed_text = f"{name}\ntechnologies: {technologies}\npatterns: {patterns}\noutcome: {outcome}\n{what_worked}\n{what_didnt}".strip()
            row = c.execute(
                "SELECT id, rowid, embed_text FROM stacks WHERE slug = ?",
                (slug,),
            ).fetchone()
            if row and row[2] == embed_text:
                continue
            vec = _embed(embed_text)
            if row:
                c.execute(
                    "UPDATE stacks SET name=?, technologies=?, patterns=?, "
                    "context=?, outcome=?, what_worked=?, what_didnt=?, "
                    "when_to_reuse=?, when_to_avoid=?, references_links=?, "
                    "last_seen=?, embed_text=? WHERE slug=?",
                    (
                        name, technologies, patterns, context, outcome,
                        what_worked, what_didnt, when_to_reuse, when_to_avoid,
                        references_links, now, embed_text, slug,
                    ),
                )
                rowid = row[1]
            else:
                st_id = uuid.uuid4().hex
                cur = c.execute(
                    "INSERT INTO stacks "
                    "(id, slug, name, technologies, patterns, context, outcome, "
                    " what_worked, what_didnt, when_to_reuse, when_to_avoid, "
                    " references_links, first_seen, last_seen, use_count, embed_text) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)",
                    (
                        st_id, slug, name, technologies, patterns, context,
                        outcome, what_worked, what_didnt, when_to_reuse,
                        when_to_avoid, references_links, now, now, embed_text,
                    ),
                )
                rowid = cur.lastrowid

            c.execute("DELETE FROM stacks_vec WHERE rowid = ?", (rowid,))
            c.execute(
                "INSERT INTO stacks_vec (rowid, embedding) VALUES (?, ?)",
                (rowid, vec),
            )
            indexed += 1
    return indexed


@app.get("/stacks", operation_id="list_stacks")
def list_stacks(outcome: str | None = None) -> dict[str, Any]:
    """List recorded stack experiments.  Filter by outcome=
    success|partial|failure|mixed."""
    _sync_stacks()
    sql = (
        "SELECT slug, name, technologies, patterns, context, outcome, "
        "what_worked, what_didnt, when_to_reuse, when_to_avoid, "
        "references_links, first_seen, last_seen, use_count FROM stacks"
    )
    params: list[Any] = []
    if outcome:
        sql += " WHERE outcome = ?"
        params.append(outcome.lower())
    sql += " ORDER BY outcome, name"
    with _conn() as c:
        rows = list(c.execute(sql, params))
    return {
        "stacks": [
            {
                "slug": r[0], "name": r[1], "technologies": r[2], "patterns": r[3],
                "context": r[4], "outcome": r[5], "what_worked": r[6],
                "what_didnt": r[7], "when_to_reuse": r[8], "when_to_avoid": r[9],
                "references": r[10], "first_seen_unix": r[11],
                "last_seen_unix": r[12], "use_count": r[13],
            }
            for r in rows
        ],
        "count": len(rows),
    }


@app.get("/stacks/{slug}", operation_id="get_stack")
def get_stack(slug: str) -> dict[str, Any]:
    _sync_stacks()
    with _conn() as c:
        row = c.execute(
            "SELECT slug, name, technologies, patterns, context, outcome, "
            "what_worked, what_didnt, when_to_reuse, when_to_avoid, "
            "references_links, first_seen, last_seen, use_count FROM stacks WHERE slug = ?",
            (slug,),
        ).fetchone()
    if not row:
        raise HTTPException(404, f"unknown stack: {slug}")
    return {
        "slug": row[0], "name": row[1], "technologies": row[2], "patterns": row[3],
        "context": row[4], "outcome": row[5], "what_worked": row[6],
        "what_didnt": row[7], "when_to_reuse": row[8], "when_to_avoid": row[9],
        "references": row[10], "first_seen_unix": row[11],
        "last_seen_unix": row[12], "use_count": row[13],
    }


class StackSearchRequest(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=50)
    outcome: str | None = None


@app.post("/stacks/search", operation_id="search_stacks")
def search_stacks(req: StackSearchRequest) -> dict[str, Any]:
    """Semantic search across stack records."""
    _sync_stacks()
    q = _embed(req.query)
    with _conn() as c:
        if req.outcome:
            rows = list(c.execute(
                """
                SELECT stacks.slug, stacks.name, stacks.technologies, stacks.outcome,
                       stacks.what_worked, stacks.what_didnt, stacks.use_count,
                       stacks_vec.distance
                FROM stacks_vec
                JOIN stacks ON stacks.rowid = stacks_vec.rowid
                WHERE stacks_vec.embedding MATCH ? AND k = ?
                  AND stacks.outcome = ?
                ORDER BY stacks_vec.distance
                """,
                (q, req.limit, req.outcome.lower()),
            ))
        else:
            rows = list(c.execute(
                """
                SELECT stacks.slug, stacks.name, stacks.technologies, stacks.outcome,
                       stacks.what_worked, stacks.what_didnt, stacks.use_count,
                       stacks_vec.distance
                FROM stacks_vec
                JOIN stacks ON stacks.rowid = stacks_vec.rowid
                WHERE stacks_vec.embedding MATCH ? AND k = ?
                ORDER BY stacks_vec.distance
                """,
                (q, req.limit),
            ))
    return {
        "query": req.query, "outcome": req.outcome,
        "matches": [
            {
                "slug": r[0], "name": r[1], "technologies": r[2],
                "outcome": r[3], "what_worked": r[4], "what_didnt": r[5],
                "use_count": r[6], "distance": r[7],
            }
            for r in rows
        ],
    }


@app.post("/stacks/{slug}/use", operation_id="log_stack_use")
def log_stack_use(slug: str, notes: str = "") -> dict[str, Any]:
    """Bump use_count when this stack record is consulted to make a real
    decision (reuse or avoid)."""
    with _conn() as c:
        row = c.execute("SELECT id FROM stacks WHERE slug = ?", (slug,)).fetchone()
        if not row:
            raise HTTPException(404, f"unknown stack: {slug}")
        c.execute(
            "UPDATE stacks SET use_count = use_count + 1, last_seen = ? WHERE slug = ?",
            (int(time.time()), slug),
        )
    _audit("stack.use", {"slug": slug, "notes": notes[:200]})
    return {"slug": slug, "action": "use_count_bumped"}


# ---------------------------------------------------------------------------
# Commands — building-block console invocations with gotchas + cross-
# platform equivalents.  Auto-indexed from commands/<family>/<slug>.md.
# ---------------------------------------------------------------------------
def _sync_commands() -> int:
    if not COMMANDS_DIR.is_dir():
        return 0
    paths = sorted(COMMANDS_DIR.glob("**/*.md"))
    if not paths:
        return 0
    indexed = 0
    now = int(time.time())
    with _conn() as c:
        for p in paths:
            meta, body = _parse_md_frontmatter(p)
            slug = meta.get("slug") or p.stem
            name = meta.get("name") or slug.replace("-", " ")
            family = (
                meta.get("family")
                or (p.parent.name if p.parent != COMMANDS_DIR else "uncategorized")
            )
            platform = meta.get("platform") or ""
            equivalents = meta.get("equivalents") or ""
            references_links = meta.get("references") or ""

            command_section = _extract_section(body, "Command") or _extract_section(body, "Invocation")
            command_line = _extract_first_code_block(command_section) if command_section else (command_section or "").strip()
            when_to_use = _extract_section(body, "When to use") or _extract_section(body, "When")
            when_not_to_use = _extract_section(body, "When NOT to use") or _extract_section(body, "When NOT")
            gotchas = _extract_section(body, "Gotchas") or _extract_section(body, "Pitfalls")
            flags = _extract_section(body, "Flags") or _extract_section(body, "Options") or _extract_section(body, "Flag tour")
            examples = _extract_section(body, "Examples") or _extract_section(body, "Example")

            if not command_line:
                continue

            embed_text = (
                f"{name}\n{family}\n{command_line}\n"
                f"{when_to_use}\n{gotchas}"
            ).strip()
            row = c.execute(
                "SELECT id, rowid, embed_text FROM commands WHERE slug = ?",
                (slug,),
            ).fetchone()
            if row and row[2] == embed_text:
                continue
            vec = _embed(embed_text)
            if row:
                c.execute(
                    "UPDATE commands SET name=?, family=?, command_line=?, "
                    "platform=?, equivalents=?, when_to_use=?, when_not_to_use=?, "
                    "gotchas=?, flags_explained=?, examples=?, references_links=?, "
                    "last_seen=?, embed_text=? WHERE slug=?",
                    (
                        name, family, command_line, platform, equivalents,
                        when_to_use, when_not_to_use, gotchas, flags, examples,
                        references_links, now, embed_text, slug,
                    ),
                )
                rowid = row[1]
            else:
                cmd_id = uuid.uuid4().hex
                cur = c.execute(
                    "INSERT INTO commands "
                    "(id, slug, name, family, command_line, platform, equivalents, "
                    " when_to_use, when_not_to_use, gotchas, flags_explained, "
                    " examples, references_links, first_seen, last_seen, use_count, embed_text) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)",
                    (
                        cmd_id, slug, name, family, command_line, platform,
                        equivalents, when_to_use, when_not_to_use, gotchas,
                        flags, examples, references_links, now, now, embed_text,
                    ),
                )
                rowid = cur.lastrowid

            c.execute("DELETE FROM commands_vec WHERE rowid = ?", (rowid,))
            c.execute(
                "INSERT INTO commands_vec (rowid, embedding) VALUES (?, ?)",
                (rowid, vec),
            )
            indexed += 1
    return indexed


@app.get("/commands", operation_id="list_commands")
def list_commands(family: str | None = None, platform: str | None = None) -> dict[str, Any]:
    """List catalogued console commands.  Filter by family (package-mgmt,
    container, git, fs, net-ssh, perms, systemd, monitoring, certs, text,
    process) or platform tag (debian, ubuntu, fedora, macos, windows,
    cross-platform)."""
    _sync_commands()
    sql = (
        "SELECT slug, name, family, command_line, platform, equivalents, "
        "when_to_use, when_not_to_use, gotchas, flags_explained, examples, "
        "references_links, first_seen, last_seen, use_count FROM commands"
    )
    params: list[Any] = []
    if family:
        sql += " WHERE family = ?"
        params.append(family)
    sql += " ORDER BY family, name"
    with _conn() as c:
        rows = list(c.execute(sql, params))
    items = [
        {
            "slug": r[0], "name": r[1], "family": r[2],
            "command_line": r[3], "platform": r[4], "equivalents": r[5],
            "when_to_use": r[6], "when_not_to_use": r[7],
            "gotchas": r[8], "flags_explained": r[9], "examples": r[10],
            "references": r[11], "first_seen_unix": r[12],
            "last_seen_unix": r[13], "use_count": r[14],
        }
        for r in rows
    ]
    if platform:
        items = [c for c in items if platform in (c["platform"] or "")]
    return {"commands": items, "count": len(items)}


@app.get("/commands/{slug}", operation_id="get_command")
def get_command(slug: str) -> dict[str, Any]:
    _sync_commands()
    with _conn() as c:
        row = c.execute(
            "SELECT slug, name, family, command_line, platform, equivalents, "
            "when_to_use, when_not_to_use, gotchas, flags_explained, examples, "
            "references_links, first_seen, last_seen, use_count FROM commands WHERE slug = ?",
            (slug,),
        ).fetchone()
    if not row:
        raise HTTPException(404, f"unknown command: {slug}")
    return {
        "slug": row[0], "name": row[1], "family": row[2],
        "command_line": row[3], "platform": row[4], "equivalents": row[5],
        "when_to_use": row[6], "when_not_to_use": row[7],
        "gotchas": row[8], "flags_explained": row[9], "examples": row[10],
        "references": row[11], "first_seen_unix": row[12],
        "last_seen_unix": row[13], "use_count": row[14],
    }


class CommandSearchRequest(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=50)
    family: str | None = None


@app.post("/commands/search", operation_id="search_commands")
def search_commands(req: CommandSearchRequest) -> dict[str, Any]:
    """Semantic search across command name + command-line + when-to-use + gotchas."""
    _sync_commands()
    q = _embed(req.query)
    with _conn() as c:
        if req.family:
            rows = list(c.execute(
                """
                SELECT commands.slug, commands.name, commands.family,
                       commands.command_line, commands.gotchas, commands.use_count,
                       commands_vec.distance
                FROM commands_vec
                JOIN commands ON commands.rowid = commands_vec.rowid
                WHERE commands_vec.embedding MATCH ? AND k = ?
                  AND commands.family = ?
                ORDER BY commands_vec.distance
                """,
                (q, req.limit, req.family),
            ))
        else:
            rows = list(c.execute(
                """
                SELECT commands.slug, commands.name, commands.family,
                       commands.command_line, commands.gotchas, commands.use_count,
                       commands_vec.distance
                FROM commands_vec
                JOIN commands ON commands.rowid = commands_vec.rowid
                WHERE commands_vec.embedding MATCH ? AND k = ?
                ORDER BY commands_vec.distance
                """,
                (q, req.limit),
            ))
    return {
        "query": req.query, "family": req.family,
        "matches": [
            {
                "slug": r[0], "name": r[1], "family": r[2],
                "command_line": r[3], "gotchas": r[4],
                "use_count": r[5], "distance": r[6],
            }
            for r in rows
        ],
    }


@app.post("/commands/{slug}/use", operation_id="log_command_use")
def log_command_use(slug: str, notes: str = "") -> dict[str, Any]:
    """Bump use_count when this command is consulted for real work."""
    with _conn() as c:
        row = c.execute("SELECT id FROM commands WHERE slug = ?", (slug,)).fetchone()
        if not row:
            raise HTTPException(404, f"unknown command: {slug}")
        c.execute(
            "UPDATE commands SET use_count = use_count + 1, last_seen = ? WHERE slug = ?",
            (int(time.time()), slug),
        )
    _audit("command.use", {"slug": slug, "notes": notes[:200]})
    return {"slug": slug, "action": "use_count_bumped"}


# ---------------------------------------------------------------------------
# Delegates registry + delegation log
#
# A "delegate" is anything Claude can defer work to without using its own
# tokens: a local LLM exposed on the LAN, a MetaMCP aggregator, an SSH host
# with heavy compute, etc.  The registry tracks WHAT each delegate can do
# (capabilities), HOW to reach it (contact_json — protocol + url + ssh
# details), and HOW WELL it actually does it (per-capability stats derived
# from the append-only delegation_log).
#
# The point of the log is to let future-Claude make grounded decisions
# about whether to defer.  If `local-llm` has 90% success rate on
# "log-skim" over 12 attempts, defer log-skim to it.  If it's 30% on
# "code-snippet-extraction" over 5 attempts, do that in-Claude.
# ---------------------------------------------------------------------------
class DelegateContact(BaseModel):
    protocol: str | None = None
    url: str | None = None
    ssh: dict[str, str] | None = None
    auth_header: str | None = None
    extra: dict[str, Any] | None = None


class DelegateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    kind: str = Field(..., description="llm | mcp | tool | host | other")
    contact: DelegateContact = Field(default_factory=DelegateContact)
    capabilities: list[str] = Field(default_factory=list)
    notes: str = ""
    enabled: bool = True


class DelegatePatch(BaseModel):
    kind: str | None = None
    contact: DelegateContact | None = None
    capabilities: list[str] | None = None
    notes: str | None = None
    enabled: bool | None = None


class DelegationLogCreate(BaseModel):
    delegate: str = Field(..., description="delegate name")
    capability: str = Field(..., min_length=1)
    task_summary: str = Field(..., min_length=1, max_length=500)
    outcome: str = Field(..., description="success | partial | failure | refused")
    latency_ms: int | None = None
    token_savings: int | None = Field(
        default=None, description="estimated Claude tokens NOT spent because of the delegation"
    )
    notes: str = ""


def _delegate_stats(c: sqlite3.Connection, delegate_id: str) -> dict[str, Any]:
    """Aggregate per-capability outcomes for one delegate."""
    rows = list(
        c.execute(
            """
            SELECT capability, outcome, COUNT(*),
                   AVG(latency_ms), SUM(COALESCE(token_savings, 0))
            FROM delegation_log
            WHERE delegate_id = ?
            GROUP BY capability, outcome
            """,
            (delegate_id,),
        )
    )
    by_cap: dict[str, dict[str, Any]] = {}
    for cap, outcome, n, avg_latency, tokens_saved in rows:
        slot = by_cap.setdefault(cap, {"capability": cap, "n": 0, "by_outcome": {},
                                       "avg_latency_ms": None, "token_savings": 0})
        slot["n"] += n
        slot["by_outcome"][outcome] = slot["by_outcome"].get(outcome, 0) + n
        slot["token_savings"] += int(tokens_saved or 0)
        # Average latency over all outcomes weighted by count; correct as a
        # weighted avg of avg-per-outcome — but sqlite gave us avg per (cap,
        # outcome) pair already, so weight each in.
        if avg_latency is not None:
            prev = slot["avg_latency_ms"]
            slot["avg_latency_ms"] = (
                (prev * (slot["n"] - n) + avg_latency * n) / slot["n"]
                if prev is not None
                else avg_latency
            )
    # Derive success_rate per capability.
    for cap_slot in by_cap.values():
        wins = cap_slot["by_outcome"].get("success", 0) + 0.5 * cap_slot["by_outcome"].get("partial", 0)
        cap_slot["success_rate"] = wins / cap_slot["n"] if cap_slot["n"] else None
    return {"per_capability": list(by_cap.values()), "total_attempts": sum(c["n"] for c in by_cap.values())}


def _delegate_row_to_dict(r: tuple) -> dict[str, Any]:
    return {
        "id": r[0],
        "name": r[1],
        "kind": r[2],
        "contact": json.loads(r[3]),
        "capabilities": json.loads(r[4]),
        "notes": r[5],
        "added_at_unix": r[6],
        "enabled": bool(r[7]),
    }


@app.get("/delegates", operation_id="list_delegates")
def list_delegates(include_stats: bool = True) -> dict[str, Any]:
    """List all delegates with their per-capability success-rate stats."""
    with _conn() as c:
        rows = list(
            c.execute(
                "SELECT id, name, kind, contact_json, capabilities_json, "
                "notes, added_at, enabled FROM delegates ORDER BY enabled DESC, name"
            )
        )
        delegates = []
        for r in rows:
            entry = _delegate_row_to_dict(r)
            if include_stats:
                entry["stats"] = _delegate_stats(c, entry["id"])
            delegates.append(entry)
    return {"delegates": delegates, "count": len(delegates)}


# Canonical capability vocabulary lives in the local-delegate SKILL.md table.
# Sessions reach for the natural trigger words ("summarization",
# "classification") which don't match the hyphenated canonical tags, so
# `best` used to return null and the delegation never got logged.  Normalize
# on the way in (both the `best` query and the `/delegations` write) so stats
# aggregate under one name regardless of how the caller phrased it.
_CAPABILITY_SYNONYMS = {
    "summarization": "bulk-summarization",
    "summarize": "bulk-summarization",
    "summary": "bulk-summarization",
    "summarisation": "bulk-summarization",
    "log-skimming": "log-skim",
    "log-analysis": "log-skim",
    "log-search": "log-skim",
    "doc-reading": "doc-skim",
    "doc-read": "doc-skim",
    "document-skim": "doc-skim",
    "doc-search": "doc-skim",
    "classification": "yes-no-classification",
    "classify": "yes-no-classification",
    "categorization": "yes-no-classification",
    "labeling": "yes-no-classification",
    "code-extraction": "code-snippet-extraction",
    "snippet-extraction": "code-snippet-extraction",
    "code-snippet": "code-snippet-extraction",
    "extract-code": "code-snippet-extraction",
    "embeddings": "embedding",
    "embedding-generation": "embedding",
    "embed": "embedding",
    "vectorize": "embedding",
    "mcp-aggregation": "mcp-tool-aggregation",
    "tool-aggregation": "mcp-tool-aggregation",
    "mcp-proxy": "remote-mcp-proxy",
    "mcp-relay": "remote-mcp-proxy",
    "shell-exec": "shell-exec-bulk",
    "remote-shell": "shell-exec-bulk",
    "bulk-shell": "shell-exec-bulk",
    "transcode": "transcoding",
    "video-transcode": "transcoding",
    "audio-transcode": "transcoding",
    "translate": "translation",
    "localization": "translation",
}


def _canon_capability(cap: str) -> str:
    """Normalize a capability name to its canonical tag: lowercase, trim,
    collapse spaces/underscores to hyphens, then map known synonyms."""
    norm = "-".join(str(cap).strip().lower().split())
    norm = norm.replace("_", "-")
    while "--" in norm:
        norm = norm.replace("--", "-")
    return _CAPABILITY_SYNONYMS.get(norm, norm)


@app.get("/delegates/best", operation_id="best_delegate")
def best_delegate_for_capability(
    capability: str,
    min_attempts: int = 0,
    min_success_rate: float = 0.0,
) -> dict[str, Any]:
    """Pick the best enabled delegate for a capability.  Best = highest
    success rate, with a floor on attempt count to weed out one-shot flukes.
    Returns null if no enabled delegate meets the bar — the caller should
    fall back to in-Claude execution."""
    capability = _canon_capability(capability)
    with _conn() as c:
        rows = list(
            c.execute(
                "SELECT id, name, kind, contact_json, capabilities_json, "
                "notes, added_at, enabled FROM delegates WHERE enabled = 1"
            )
        )
        candidates = []
        for r in rows:
            entry = _delegate_row_to_dict(r)
            if capability not in entry["capabilities"]:
                continue
            stats = _delegate_stats(c, entry["id"])
            cap_stat = next(
                (s for s in stats["per_capability"] if s["capability"] == capability),
                None,
            )
            if cap_stat is None:
                # Never tried — score as 0.5 with 0 attempts so a never-tried
                # delegate beats nothing, but loses to anything proven.
                rate, n = 0.5, 0
            else:
                rate = cap_stat["success_rate"] or 0.0
                n = cap_stat["n"]
            if n < min_attempts or rate < min_success_rate:
                continue
            entry["capability"] = capability
            entry["success_rate"] = rate
            entry["attempts"] = n
            candidates.append(entry)
    candidates.sort(key=lambda d: (d["success_rate"], d["attempts"]), reverse=True)
    return {
        "capability": capability,
        "best": candidates[0] if candidates else None,
        "all_candidates": candidates,
    }


@app.get("/delegates/{name}", operation_id="get_delegate")
def get_delegate(name: str) -> dict[str, Any]:
    with _conn() as c:
        row = c.execute(
            "SELECT id, name, kind, contact_json, capabilities_json, "
            "notes, added_at, enabled FROM delegates WHERE name = ?",
            (name,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"unknown delegate: {name}")
        entry = _delegate_row_to_dict(row)
        entry["stats"] = _delegate_stats(c, entry["id"])
        recent = list(
            c.execute(
                "SELECT capability, task_summary, outcome, latency_ms, "
                "token_savings, notes, ts_unix_ms FROM delegation_log "
                "WHERE delegate_id = ? ORDER BY ts_unix_ms DESC LIMIT 25",
                (entry["id"],),
            )
        )
        entry["recent_log"] = [
            {
                "capability": r[0],
                "task_summary": r[1],
                "outcome": r[2],
                "latency_ms": r[3],
                "token_savings": r[4],
                "notes": r[5],
                "ts_unix_ms": r[6],
            }
            for r in recent
        ]
    return entry


@app.post("/delegates", operation_id="create_delegate")
def create_delegate(req: DelegateCreate) -> dict[str, Any]:
    with _conn() as c:
        existing = c.execute(
            "SELECT id FROM delegates WHERE name = ?", (req.name,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail=f"delegate {req.name} already exists — PATCH /delegates/{req.name} to edit")
        del_id = uuid.uuid4().hex
        c.execute(
            "INSERT INTO delegates (id, name, kind, contact_json, "
            "capabilities_json, notes, added_at, enabled) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                del_id,
                req.name,
                req.kind,
                req.contact.model_dump_json(exclude_none=True),
                json.dumps(req.capabilities, sort_keys=True),
                req.notes,
                int(time.time()),
                1 if req.enabled else 0,
            ),
        )
    _audit("delegate.created", {"name": req.name, "kind": req.kind, "capabilities": req.capabilities})
    return {"id": del_id, "name": req.name, "action": "created"}


@app.patch("/delegates/{name}", operation_id="patch_delegate")
def patch_delegate(name: str, req: DelegatePatch) -> dict[str, Any]:
    with _conn() as c:
        row = c.execute(
            "SELECT id, kind, contact_json, capabilities_json, notes, enabled "
            "FROM delegates WHERE name = ?",
            (name,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"unknown delegate: {name}")
        del_id, kind, contact_json, caps_json, notes, enabled = row
        new_kind = req.kind if req.kind is not None else kind
        new_contact = (
            req.contact.model_dump_json(exclude_none=True)
            if req.contact is not None
            else contact_json
        )
        new_caps = (
            json.dumps(req.capabilities, sort_keys=True)
            if req.capabilities is not None
            else caps_json
        )
        new_notes = req.notes if req.notes is not None else notes
        new_enabled = (1 if req.enabled else 0) if req.enabled is not None else enabled
        c.execute(
            "UPDATE delegates SET kind=?, contact_json=?, capabilities_json=?, "
            "notes=?, enabled=? WHERE id=?",
            (new_kind, new_contact, new_caps, new_notes, new_enabled, del_id),
        )
    _audit("delegate.patched", {"name": name})
    return {"name": name, "action": "patched"}


@app.delete("/delegates/{name}", operation_id="delete_delegate")
def delete_delegate(name: str) -> dict[str, Any]:
    with _conn() as c:
        row = c.execute(
            "SELECT id FROM delegates WHERE name = ?", (name,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"unknown delegate: {name}")
        # Soft-delete to preserve the log history.  enabled=0 hides it from
        # /delegates/best.  Use SQL directly if a true purge is wanted.
        c.execute("UPDATE delegates SET enabled = 0 WHERE id = ?", (row[0],))
    _audit("delegate.disabled", {"name": name})
    return {"name": name, "action": "disabled (soft-delete; history preserved)"}


@app.post("/delegations", operation_id="log_delegation")
def log_delegation(req: DelegationLogCreate) -> dict[str, Any]:
    if req.outcome not in {"success", "partial", "failure", "refused"}:
        raise HTTPException(status_code=400, detail=f"unknown outcome: {req.outcome}")
    capability = _canon_capability(req.capability)
    with _conn() as c:
        row = c.execute(
            "SELECT id FROM delegates WHERE name = ?", (req.delegate,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"unknown delegate: {req.delegate}")
        del_id = row[0]
        c.execute(
            "INSERT INTO delegation_log "
            "(delegate_id, capability, task_summary, outcome, latency_ms, "
            "token_savings, notes, ts_unix_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                del_id,
                capability,
                req.task_summary,
                req.outcome,
                req.latency_ms,
                req.token_savings,
                req.notes,
                int(time.time() * 1000),
            ),
        )
    _audit(
        "delegation.logged",
        {
            "delegate": req.delegate,
            "capability": capability,
            "outcome": req.outcome,
            "latency_ms": req.latency_ms,
        },
    )
    return {"delegate": req.delegate, "outcome": req.outcome, "action": "logged"}


@app.get("/delegations", operation_id="list_delegations")
def list_delegations(
    delegate: str | None = None,
    capability: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    limit = max(1, min(500, limit))
    where: list[str] = []
    params: list[Any] = []
    if delegate:
        with _conn() as c:
            row = c.execute("SELECT id FROM delegates WHERE name = ?", (delegate,)).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"unknown delegate: {delegate}")
            where.append("delegate_id = ?")
            params.append(row[0])
    if capability:
        where.append("capability = ?")
        params.append(capability)
    sql = ("SELECT delegate_id, capability, task_summary, outcome, latency_ms, "
           "token_savings, notes, ts_unix_ms FROM delegation_log")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY ts_unix_ms DESC LIMIT ?"
    params.append(limit)
    with _conn() as c:
        rows = list(c.execute(sql, params))
        # resolve delegate name once
        names = {
            r[0]: r[1]
            for r in c.execute("SELECT id, name FROM delegates")
        }
    return {
        "events": [
            {
                "delegate": names.get(r[0], r[0]),
                "capability": r[1],
                "task_summary": r[2],
                "outcome": r[3],
                "latency_ms": r[4],
                "token_savings": r[5],
                "notes": r[6],
                "ts_unix_ms": r[7],
            }
            for r in rows
        ],
        "count": len(rows),
    }


@app.get("/delegations/stats", operation_id="delegations_stats")
def delegations_stats() -> dict[str, Any]:
    """Token-savings dashboard data.

    Aggregates the delegation_log into four shapes the GUI needs in
    one round-trip:

      - `totals`: lifetime + rolling 24h / 7d / 30d sums of token_savings,
        with companion call counts.  When token_savings is null we still
        count the call so the success rate stays honest.
      - `per_delegate`: name + total_saved + n_calls + success_rate, sorted
        by total_saved desc.  Drives the "who's pulling weight" table.
      - `per_capability`: same shape keyed by capability.  Drives the
        "what kind of work pays off" table.
      - `daily_30d`: list of {date, saved, calls} for the last 30 calendar
        days (UTC), oldest first.  Powers the sparkline.

    All token counts are best-effort estimates the dispatcher logged at
    call time (prompt_chars + response_chars // 4 is the typical formula
    in scripts/dispatch-with-rag.py); they're a useful ballpark, not a
    billing source of truth.
    """
    now_ms = int(time.time() * 1000)
    day_ms = 24 * 60 * 60 * 1000
    horizon_24h = now_ms - day_ms
    horizon_7d = now_ms - 7 * day_ms
    horizon_30d = now_ms - 30 * day_ms

    with _conn() as c:
        # Lifetime + windowed totals.  COALESCE so a window with zero calls
        # returns 0, not null.
        row = c.execute(
            "SELECT "
            "  COALESCE(SUM(token_savings), 0), COUNT(*), "
            "  COALESCE(SUM(CASE WHEN ts_unix_ms >= ? THEN token_savings ELSE 0 END), 0), "
            "  SUM(CASE WHEN ts_unix_ms >= ? THEN 1 ELSE 0 END), "
            "  COALESCE(SUM(CASE WHEN ts_unix_ms >= ? THEN token_savings ELSE 0 END), 0), "
            "  SUM(CASE WHEN ts_unix_ms >= ? THEN 1 ELSE 0 END), "
            "  COALESCE(SUM(CASE WHEN ts_unix_ms >= ? THEN token_savings ELSE 0 END), 0), "
            "  SUM(CASE WHEN ts_unix_ms >= ? THEN 1 ELSE 0 END) "
            "FROM delegation_log",
            (horizon_24h, horizon_24h, horizon_7d, horizon_7d, horizon_30d, horizon_30d),
        ).fetchone()
        lifetime_saved, lifetime_calls = int(row[0] or 0), int(row[1] or 0)
        saved_24h, calls_24h = int(row[2] or 0), int(row[3] or 0)
        saved_7d, calls_7d = int(row[4] or 0), int(row[5] or 0)
        saved_30d, calls_30d = int(row[6] or 0), int(row[7] or 0)

        # Per-delegate rollup.  Join the delegate name once so the response
        # is GUI-ready without a follow-up lookup.
        per_del_rows = list(
            c.execute(
                "SELECT d.name, "
                "  COALESCE(SUM(l.token_savings), 0), "
                "  COUNT(*), "
                "  SUM(CASE WHEN l.outcome = 'success' THEN 1 ELSE 0 END) "
                "FROM delegation_log l JOIN delegates d ON d.id = l.delegate_id "
                "GROUP BY d.name "
                "ORDER BY 2 DESC",
            )
        )

        # Per-capability rollup.  capability is a free-text column, so just
        # group on it directly.
        per_cap_rows = list(
            c.execute(
                "SELECT capability, "
                "  COALESCE(SUM(token_savings), 0), "
                "  COUNT(*), "
                "  SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) "
                "FROM delegation_log "
                "GROUP BY capability "
                "ORDER BY 2 DESC",
            )
        )

        # Daily time-series for the last 30 days.  SQLite's date() coerces
        # the unix-ms / 1000 -> 'YYYY-MM-DD' (UTC).  We materialize the full
        # 30-day range client-side from what comes back so missing days stay
        # at 0.
        daily_rows = list(
            c.execute(
                "SELECT date(ts_unix_ms / 1000, 'unixepoch') AS d, "
                "  COALESCE(SUM(token_savings), 0), COUNT(*) "
                "FROM delegation_log "
                "WHERE ts_unix_ms >= ? "
                "GROUP BY d ORDER BY d",
                (horizon_30d,),
            )
        )

    by_day = {r[0]: (int(r[1] or 0), int(r[2] or 0)) for r in daily_rows}
    # Build a contiguous 30-day window ending TODAY (UTC).  Using a 30-day
    # horizon for the SQL query but indexing the buckets from (today - 29)
    # ensures the current day is the last bar in the sparkline; otherwise
    # the chart looks stale because it always lags by a day.
    now_s = int(now_ms // 1000)
    today_midnight_utc = (now_s // 86400) * 86400
    daily_30d: list[dict[str, Any]] = []
    for i in range(30):
        day_unix = today_midnight_utc - (29 - i) * 86400
        date_str = time.strftime("%Y-%m-%d", time.gmtime(day_unix))
        saved, calls = by_day.get(date_str, (0, 0))
        daily_30d.append({"date": date_str, "saved": saved, "calls": calls})

    def _to_per_row(r: tuple[Any, ...]) -> dict[str, Any]:
        name, saved, n_calls, n_success = r
        n_calls = int(n_calls or 0)
        n_success = int(n_success or 0)
        return {
            "name": name,
            "total_saved": int(saved or 0),
            "n_calls": n_calls,
            "n_success": n_success,
            "success_rate": (n_success / n_calls) if n_calls else 0.0,
        }

    return {
        "totals": {
            "lifetime_saved": lifetime_saved,
            "lifetime_calls": lifetime_calls,
            "last_24h_saved": saved_24h,
            "last_24h_calls": calls_24h,
            "last_7d_saved": saved_7d,
            "last_7d_calls": calls_7d,
            "last_30d_saved": saved_30d,
            "last_30d_calls": calls_30d,
        },
        "per_delegate": [_to_per_row(r) for r in per_del_rows],
        "per_capability": [_to_per_row(r) for r in per_cap_rows],
        "daily_30d": daily_30d,
    }


# ---------------------------------------------------------------------------
# Audit log (read-only)
# ---------------------------------------------------------------------------
@app.get("/audit", operation_id="list_audit")
def list_audit(limit: int = 50) -> dict[str, Any]:
    limit = max(1, min(500, limit))
    with _conn() as c:
        rows = list(
            c.execute(
                "SELECT ts_unix_ms, kind, payload_json FROM audit_log "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            )
        )
    return {
        "events": [
            {"ts_unix_ms": r[0], "kind": r[1], "payload": json.loads(r[2])}
            for r in rows
        ],
        "count": len(rows),
    }


# ---------------------------------------------------------------------------
# GUI mutation endpoints (added 2026-06-17) — vault reveal/delete, script
# view/edit/delete, and catalog-row deletes. Used by the single-page explorer.
# ---------------------------------------------------------------------------
@app.get("/vault/{key}/reveal", operation_id="vault_reveal")
def vault_reveal(key: str) -> dict[str, Any]:
    """Return ONE secret's plaintext value for the GUI reveal button. The value
    travels server->browser only; it is never logged (audited by NAME only)."""
    v = _load_vault()
    if key not in v:
        raise HTTPException(404, f"unknown secret: {key}")
    _audit("vault.reveal", {"key": key})
    return {"name": key, "value": v[key]}


@app.delete("/vault/{key}", operation_id="vault_delete")
def vault_delete(key: str) -> dict[str, Any]:
    """Remove a secret from the vault JSON (preserves the rest of the file)."""
    try:
        raw = json.loads(VAULT_PATH.read_text(encoding="utf-8")) if VAULT_PATH.exists() else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(500, f"vault: malformed JSON: {exc}") from exc
    if not isinstance(raw, dict) or key not in raw:
        raise HTTPException(404, f"unknown secret: {key}")
    del raw[key]
    VAULT_PATH.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    _audit("vault.deleted", {"key": key})
    return {"name": key, "action": "deleted"}


def _safe_script_name(name: str) -> None:
    if "/" in name or "\\" in name or name in ("", ".", ".."):
        raise HTTPException(400, "invalid script name (bare filename only)")


@app.get("/scripts/{name}/content", operation_id="get_script_content")
def get_script_content(name: str) -> dict[str, Any]:
    """Raw file text of a script, for the GUI view/edit panel."""
    _safe_script_name(name)
    p = SCRIPTS_DIR / name
    if not p.is_file():
        raise HTTPException(404, f"unknown script: {name}")
    return {"name": name, "path": str(p), "content": p.read_text(encoding="utf-8")}


class ScriptContent(BaseModel):
    content: str


@app.put("/scripts/{name}", operation_id="put_script")
def put_script(name: str, req: ScriptContent) -> dict[str, Any]:
    """Create or overwrite a script file, then reindex it."""
    _safe_script_name(name)
    p = SCRIPTS_DIR / name
    existed = p.is_file()
    p.write_text(req.content, encoding="utf-8")
    try:
        p.chmod(0o755)
    except OSError:
        pass  # drvfs ignores chmod — non-fatal
    _sync_scripts()
    _audit("script." + ("updated" if existed else "created"), {"name": name})
    return {"name": name, "action": "updated" if existed else "created"}


@app.delete("/scripts/{name}", operation_id="delete_script")
def delete_script(name: str) -> dict[str, Any]:
    """Delete a script file and prune its index row."""
    _safe_script_name(name)
    p = SCRIPTS_DIR / name
    if not p.is_file():
        raise HTTPException(404, f"unknown script: {name}")
    p.unlink()
    with _conn() as c:
        c.execute("DELETE FROM script_index WHERE path = ?", (str(p),))
    _audit("script.deleted", {"name": name})
    return {"name": name, "action": "deleted"}


# Catalog deletes: each table X has a companion X_vec virtual table keyed by
# rowid; remove both. Table names come from this fixed internal map (never user
# input), so the f-string interpolation is safe; slug is always parameterized.
_CATALOG_TABLES = {
    "anti-patterns": "anti_patterns",
    "design-patterns": "design_patterns",
    "technologies": "technologies",
    "snippets": "snippets",
    "stacks": "stacks",
    "commands": "commands",
    "prompts": "prompts",
}
# Source dirs for the file-backed catalogs — a real delete must remove the
# backing .md too, else the next _sync resurrects the DB row. (anti-patterns
# added via the API are DB-only; the glob simply finds nothing, which is fine.)
_CATALOG_DIRS = {
    "anti-patterns": ANTI_PATTERNS_DIR,
    "design-patterns": DESIGN_PATTERNS_DIR,
    "technologies": TECHNOLOGIES_DIR,
    "snippets": SNIPPETS_DIR,
    "stacks": STACKS_DIR,
    "commands": COMMANDS_DIR,
    "prompts": PROMPTS_DIR,
}


def _delete_catalog(entity: str, slug: str) -> dict[str, Any]:
    table = _CATALOG_TABLES[entity]
    with _conn() as c:
        row = c.execute(f"SELECT rowid FROM {table} WHERE slug = ?", (slug,)).fetchone()
        if not row:
            raise HTTPException(404, f"unknown {entity}: {slug}")
        rowid = row[0]
        c.execute(f"DELETE FROM {table}_vec WHERE rowid = ?", (rowid,))
        c.execute(f"DELETE FROM {table} WHERE rowid = ?", (rowid,))
    removed_file = False
    d = _CATALOG_DIRS.get(entity)
    if d and d.is_dir():
        for f in d.glob(f"**/{slug}.md"):
            try:
                f.unlink()
                removed_file = True
            except OSError:
                pass
    _audit(table + ".deleted", {"slug": slug, "file_removed": removed_file})
    return {"slug": slug, "action": "deleted", "file_removed": removed_file}


@app.delete("/anti-patterns/{slug}", operation_id="delete_anti_pattern")
def delete_anti_pattern(slug: str) -> dict[str, Any]:
    return _delete_catalog("anti-patterns", slug)


@app.delete("/design-patterns/{slug}", operation_id="delete_design_pattern")
def delete_design_pattern(slug: str) -> dict[str, Any]:
    return _delete_catalog("design-patterns", slug)


@app.delete("/technologies/{slug}", operation_id="delete_technology")
def delete_technology(slug: str) -> dict[str, Any]:
    return _delete_catalog("technologies", slug)


@app.delete("/snippets/{slug}", operation_id="delete_snippet")
def delete_snippet(slug: str) -> dict[str, Any]:
    return _delete_catalog("snippets", slug)


@app.delete("/stacks/{slug}", operation_id="delete_stack")
def delete_stack(slug: str) -> dict[str, Any]:
    return _delete_catalog("stacks", slug)


@app.delete("/commands/{slug}", operation_id="delete_command")
def delete_command(slug: str) -> dict[str, Any]:
    return _delete_catalog("commands", slug)


# ---------------------------------------------------------------------------
# Prompts — reusable parameterized prompts (project-init, review/debug,
# research/design, delivery, efficiency). File-backed: prompts/<category>/<slug>.md
# with a `# Prompt` section (body, may use ${PLACEHOLDER} tokens), optional
# `# Placeholders` and `# When to use` sections. Mirrors the snippets pipeline.
# ---------------------------------------------------------------------------
def _sync_prompts() -> int:
    if not PROMPTS_DIR.is_dir():
        return 0
    paths = sorted(PROMPTS_DIR.glob("**/*.md"))
    if not paths:
        return 0
    indexed = 0
    now = int(time.time())
    with _conn() as c:
        for p in paths:
            meta, body = _parse_md_frontmatter(p)
            slug = meta.get("slug") or p.stem
            name = meta.get("name") or slug.replace("-", " ")
            category = meta.get("category") or (
                p.parent.name if p.parent != PROMPTS_DIR else "general"
            )
            tags = meta.get("tags") or ""
            references_links = meta.get("references") or ""

            prompt_section = _extract_section(body, "Prompt")
            prompt_body = (prompt_section or "").strip()
            fenced = _CODE_FENCE_RE.search(prompt_body)
            if fenced:
                prompt_body = fenced.group(1).strip()
            placeholders_section = _extract_section(body, "Placeholders")
            placeholders = (
                _parse_placeholders_section(placeholders_section)
                if placeholders_section else []
            )
            when_to_use = _extract_section(body, "When to use") or _extract_section(body, "When")
            if not prompt_body:
                continue

            embed_text = f"{name}\n{category}\n{when_to_use}\n{tags}".strip()
            row = c.execute(
                "SELECT id, rowid, embed_text FROM prompts WHERE slug = ?", (slug,)
            ).fetchone()
            if row and row[2] == embed_text:
                continue
            vec = _embed(embed_text)
            placeholders_json = json.dumps(placeholders, sort_keys=True)
            if row:
                c.execute(
                    "UPDATE prompts SET name=?, category=?, body=?, placeholders_json=?, "
                    "when_to_use=?, tags=?, references_links=?, last_seen=?, embed_text=? WHERE slug=?",
                    (name, category, prompt_body, placeholders_json, when_to_use,
                     tags, references_links, now, embed_text, slug),
                )
                rowid = row[1]
            else:
                pr_id = uuid.uuid4().hex
                cur = c.execute(
                    "INSERT INTO prompts (id, slug, name, category, body, placeholders_json, "
                    "when_to_use, tags, references_links, first_seen, last_seen, use_count, embed_text) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)",
                    (pr_id, slug, name, category, prompt_body, placeholders_json,
                     when_to_use, tags, references_links, now, now, embed_text),
                )
                rowid = cur.lastrowid
            c.execute("DELETE FROM prompts_vec WHERE rowid = ?", (rowid,))
            c.execute("INSERT INTO prompts_vec (rowid, embedding) VALUES (?, ?)", (rowid, vec))
            indexed += 1
    return indexed


_PROMPT_COLS = (
    "SELECT slug, name, category, body, placeholders_json, when_to_use, "
    "tags, references_links, first_seen, last_seen, use_count FROM prompts"
)


def _prompt_row_dict(r: Any) -> dict[str, Any]:
    return {
        "slug": r[0], "name": r[1], "category": r[2], "body": r[3],
        "placeholders": json.loads(r[4] or "[]"), "when_to_use": r[5],
        "tags": r[6], "references": r[7], "first_seen_unix": r[8],
        "last_seen_unix": r[9], "use_count": r[10],
    }


@app.get("/prompts", operation_id="list_prompts")
def list_prompts(
    category: str | None = None, limit: int | None = None, offset: int = 0
) -> dict[str, Any]:
    """List reusable prompts. Filter by ?category=. Supports limit/offset."""
    _sync_prompts()
    sql = _PROMPT_COLS
    params: list[Any] = []
    if category:
        sql += " WHERE category = ?"
        params.append(category)
    sql += " ORDER BY category, name"
    with _conn() as c:
        rows = list(c.execute(sql, params))
    items = [_prompt_row_dict(r) for r in rows]
    total = len(items)
    if limit is not None:
        start = max(0, offset)
        items = items[start:start + max(0, limit)]
    return {"prompts": items, "count": len(items), "total": total, "offset": max(0, offset)}


@app.get("/prompts/{slug}", operation_id="get_prompt")
def get_prompt(slug: str) -> dict[str, Any]:
    _sync_prompts()
    with _conn() as c:
        row = c.execute(_PROMPT_COLS + " WHERE slug = ?", (slug,)).fetchone()
    if not row:
        raise HTTPException(404, f"unknown prompt: {slug}")
    return _prompt_row_dict(row)


class PromptSearchRequest(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=50)
    category: str | None = None


@app.post("/prompts/search", operation_id="search_prompts")
def search_prompts(req: PromptSearchRequest) -> dict[str, Any]:
    """Semantic search across prompt name + category + when-to-use + tags."""
    _sync_prompts()
    q = _embed(req.query)
    base = (
        "SELECT prompts.slug, prompts.name, prompts.category, prompts.when_to_use, "
        "prompts.tags, prompts_vec.distance FROM prompts_vec "
        "JOIN prompts ON prompts.rowid = prompts_vec.rowid "
        "WHERE prompts_vec.embedding MATCH ? AND k = ?"
    )
    with _conn() as c:
        if req.category:
            rows = list(c.execute(
                base + " AND prompts.category = ? ORDER BY prompts_vec.distance",
                (q, req.limit, req.category)))
        else:
            rows = list(c.execute(base + " ORDER BY prompts_vec.distance", (q, req.limit)))
    _audit("prompt.search", {"query_len": len(req.query), "limit": req.limit, "hits": len(rows)})
    return {
        "query": req.query, "category": req.category,
        "matches": [
            {"slug": r[0], "name": r[1], "category": r[2], "when_to_use": r[3],
             "tags": r[4], "distance": r[5]} for r in rows
        ],
    }


class PromptExpandRequest(BaseModel):
    values: dict[str, str] = Field(default_factory=dict)


@app.post("/prompts/{slug}/expand", operation_id="expand_prompt")
def expand_prompt(slug: str, req: PromptExpandRequest) -> dict[str, Any]:
    """Substitute ${PLACEHOLDER} tokens in the prompt body with provided values."""
    _sync_prompts()
    with _conn() as c:
        row = c.execute(
            "SELECT body, placeholders_json FROM prompts WHERE slug = ?", (slug,)
        ).fetchone()
    if not row:
        raise HTTPException(404, f"unknown prompt: {slug}")
    placeholders = json.loads(row[1] or "[]")
    missing = [ph["name"] for ph in placeholders if ph["name"] not in req.values]
    out = row[0]
    for k, v in req.values.items():
        out = out.replace("${" + k + "}", v)
    return {"slug": slug, "expanded": out, "missing": missing}


@app.post("/prompts/{slug}/use", operation_id="log_prompt_use")
def log_prompt_use(slug: str, notes: str = "") -> dict[str, Any]:
    """Bump use_count when a prompt is actually applied."""
    with _conn() as c:
        row = c.execute("SELECT id FROM prompts WHERE slug = ?", (slug,)).fetchone()
        if not row:
            raise HTTPException(404, f"unknown prompt: {slug}")
        c.execute(
            "UPDATE prompts SET use_count = use_count + 1, last_seen = ? WHERE slug = ?",
            (int(time.time()), slug),
        )
    _audit("prompt.use", {"slug": slug, "notes": notes[:200]})
    return {"slug": slug, "action": "use_count_bumped"}


@app.delete("/prompts/{slug}", operation_id="delete_prompt")
def delete_prompt(slug: str) -> dict[str, Any]:
    return _delete_catalog("prompts", slug)


# ---------------------------------------------------------------------------
# Unified search — embeds the query ONCE and runs it against every catalog's
# vec table, merging results by distance. Powers the per-prompt auto-surface
# hook efficiently (one embed call, not one per surface).
# ---------------------------------------------------------------------------
class SearchAllRequest(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=25)
    per_surface: int = Field(default=3, ge=1, le=10)


# (vec_table, source_table, join_col, label_expr, slug_expr)
_SEARCH_ALL_SURFACES = [
    ("prompts_vec", "prompts", "rowid", "prompts.name", "prompts.slug"),
    ("script_vec", "script_index", "rowid", "script_index.purpose", "script_index.path"),
    ("snippets_vec", "snippets", "rowid", "snippets.name", "snippets.slug"),
    ("design_patterns_vec", "design_patterns", "rowid", "design_patterns.intent", "design_patterns.slug"),
    ("commands_vec", "commands", "rowid", "commands.name", "commands.slug"),
    ("anti_patterns_vec", "anti_patterns", "rowid", "anti_patterns.title", "anti_patterns.slug"),
]


@app.post("/search-all", operation_id="search_all")
def search_all(req: SearchAllRequest) -> dict[str, Any]:
    """Semantic search across ALL catalogs in one call (single embed). Returns
    merged matches sorted by distance, each tagged with its surface."""
    _sync_scripts()
    _sync_prompts()
    q = _embed(req.query)
    out: list[dict[str, Any]] = []
    surface_name = {
        "prompts_vec": "prompt", "script_vec": "script", "snippets_vec": "snippet",
        "design_patterns_vec": "pattern", "commands_vec": "command",
        "anti_patterns_vec": "anti-pattern",
    }
    with _conn() as c:
        for vec_t, src_t, join_col, label_expr, slug_expr in _SEARCH_ALL_SURFACES:
            try:
                rows = c.execute(
                    f"SELECT {slug_expr}, {label_expr}, {vec_t}.distance "
                    f"FROM {vec_t} JOIN {src_t} ON {src_t}.{join_col} = {vec_t}.rowid "
                    f"WHERE {vec_t}.embedding MATCH ? AND k = ? ORDER BY {vec_t}.distance",
                    (q, req.per_surface),
                ).fetchall()
            except Exception:
                continue  # a surface with no vec rows yet shouldn't break the rest
            for r in rows:
                slug = r[0]
                if src_t == "script_index":
                    slug = Path(slug).name  # script "slug" is the filename
                out.append({
                    "surface": surface_name[vec_t], "slug": slug,
                    "label": (r[1] or "").split("\n")[0][:90], "distance": r[2],
                })
    out.sort(key=lambda x: x["distance"])
    return {"query": req.query, "matches": out[:req.limit]}
