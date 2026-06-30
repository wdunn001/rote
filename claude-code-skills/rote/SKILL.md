---
name: rote
description: Use this when you're about to write a non-trivial shell script, a `.env` mutator, a deploy verifier, a git/branch sweeper, or any operation that is plausibly already solved — and ALWAYS when the operation touches secrets. Discover and run reusable, parameterized scripts + anti-patterns from the local Rote catalog BEFORE writing new code, and record new findings + scripts back. A deterministic, auditable substitute for "LLM generates and runs a shell command on the fly."
---

# Rote — Discovery + Execution Skill

There is a local Rote at `/path/to/rote/` exposing reusable, parameterized scripts and anti-pattern records via a local HTTP API (`127.0.0.1:5572`) and a terse CLI (`/path/to/rote/cli/rote`). Use it BEFORE writing new shell code.

## Hard rules (binding, no exceptions)

1. **Never write a script to `/tmp/` and run it once.** Write it to `/path/to/rote/scripts/<name>.sh` from the start. Use `rote new <name>.sh "<purpose>"` to scaffold with frontmatter pre-filled — it's no more effort than `cat > /tmp/x.sh`.
2. **Before writing any new shell of 5+ lines, run `rote find "<one-line description>"`.** If the top match has distance < 0.7, use it. If distance < 1.0, read it and decide whether to EXTEND (add a flag) vs write fresh. Only write fresh if no match resolves cleanly.
3. **For codebase-wide find-and-replace, use `find-replace-tree.sh`** — never hand-roll `find … -exec sed -i …`. The library script handles backup, glob filtering, dry-run, gitignore awareness, and binary-file skipping in one call.
4. **For copying code blocks between files, use `copy-code-block.sh`** — never Read-then-Write-line-by-line. Anchor by regex or line range, optional transform pipe, optional anchored insert vs block-replace.
5. **For SSH ops on remote hosts, use `ssh-exec.sh` or `ssh-docker-restart.sh`** — never inline `ssh user@host "complex shell"` chains. The library scripts handle timeout, latency capture, and audit logging.
6. **When an operation succeeds and you can imagine doing it again next session, promote it.** Either save it as a new library script OR add a flag to the closest existing one. The 30 seconds of frontmatter pays back forever.

## When to invoke

- About to write a `.sh` / `.py` script of any length for an operation that sounds reusable
- About to write or modify a `.env` file with secret values
- About to do a repetitive multi-step shell operation
- About to do a codebase-wide find/replace or copy code between files
- Want to record a new anti-pattern observed during the session
- Want to look up what bit a past session ("has this failure mode happened before?")

## When NOT to invoke

- One-off `ls` / `grep` / `cat` / `find` to look at one file — those are not what the library is for
- A single curl probe that fits on one line — just run it
- The user explicitly asked for a fresh implementation

## Decision flow

```
operation about to be performed?
├── touches secrets?  →  ALWAYS use library (see [[secret-handling]] skill)
├── plausibly reusable?  →  rote find "<one-line description>"
│   ├── match found (distance < 0.4)?  →  rote run <name> -- <args>
│   └── no match?  →  proceed; consider adding it to the library at the end
└── one-off / trivial  →  proceed
```

## API surface

Use the CLI for token efficiency. The CLI talks to the local HTTP API; both share the same data.

### Discovery

```bash
rote find "inject env secrets into a .env file"
# returns up to 5 ranked matches: name <TAB> distance <TAB> purpose

rote list
# all scripts: name <TAB> touches-secrets <TAB> purpose

rote show inject-env-secrets.sh
# one script's full frontmatter (path / purpose / when / secrets)
```

### Execution

```bash
rote run inject-env-secrets.sh -- --env-file /abs/path/.env --key DB_PASS
# resolves name → absolute path → exec
```

### Anti-patterns

```bash
rote ap find "apk doesn't update after rebuild"
# semantic search: slug <TAB> distance <TAB> title

rote ap list
# all anti-patterns ordered by hit count

rote ap add <slug> "<title>" "<symptom>" "<remedy>" [--cost text]
# upsert; bumps hit_count if slug exists
```

### Health + bootstrap

```bash
rote health         # API health + embed model + vec version
rote up             # start the API if it's not up (idempotent)
```

If the API isn't up, run `rote up` once at the start of the session. First run installs the venv + embedding model (~80 MB, one-time, ~2–3 min).

## Adding a new script

When you write a genuinely new piece of reusable shell, save it under the library and update the index so future sessions find it. **Fastest path:**

```bash
rote new my-script.sh "one-line purpose"
# scaffolds /path/to/rote/scripts/my-script.sh with frontmatter
# pre-filled, +x, ready to edit
```

The API auto-reindexes on next `rote list` / `find` based on file mtime.

If hand-writing:

1. Drop the file at `/path/to/rote/scripts/<name>.sh`
2. Make it executable: `chmod +x /path/to/rote/scripts/<name>.sh`
3. Add the required frontmatter (the API parses this for the index):

```bash
#!/usr/bin/env bash
# =============================================================================
# script: <name>.sh
# purpose: <one-line: what does this do>
# inputs:
#   --flag <value>    description
# outputs: stdout shape; exit codes
# touches-secrets: true|false
# when-to-use:    bullet of valid use cases
# when-NOT-to-use: bullet of cases where caller should pick something else
# added: YYYY-MM-DD
# family: <logical-slug>             # OPTIONAL; defaults to file stem
# environment: <tag>                 # OPTIONAL; defaults from extension
# =============================================================================
```

`family:` is the LOGICAL slug shared across cross-environment variants (`find-replace-tree.sh`, `.ps1`, `.py` all use `family: find-replace-tree`). `environment:` is the runtime tag — common values: `posix-bash`, `posix-zsh`, `windows-pwsh`, `windows-cmd`, `cross-python`, `cross-node`, `cross-ruby`.

4. The API auto-reindexes on next `rote list` / `find` based on file mtime, and prunes rows whose on-disk path is gone (so renames + repo moves don't leave phantoms).

## Cross-environment variants

When the same logical operation needs different runtimes (POSIX `.sh` + Windows `.ps1`), give them the same `family:` slug. Discover variants via:

```bash
rote family find-replace-tree --env windows-pwsh
# best_match: <the .ps1 variant if one exists, else "none">
# variant:    <every variant + its environment>
```

`best_match: none` = "no variant exists for this runtime — do it yourself or write one." When you write one, drop it under `scripts/` with the matching extension; the indexer picks the right `environment` automatically.

## Adding a new anti-pattern

When a session hits a new failure mode that future sessions could trip on, record it BEFORE closing the session:

```bash
rote ap add my-new-slug "Short title (one line)" "Symptom paragraph or one-liner" "Concrete remedy + commands" --cost "token impact"
```

Or write a markdown file under `/path/to/rote/anti-patterns/<slug>.md` with the frontmatter shown in existing examples. The chronicle skill should call `ap add` for every CRITICAL / HIGH severity item it generates.

## Other clients (the library is not Claude-only)

The same backend has three surfaces — pick by what you're driving:

| Client | Surface | Path |
|---|---|---|
| Claude Code (this skill) | Bash + Read/Write/Edit + skills | `/path/to/rote/cli/rote` |
| Any MCP client (Claude Desktop, Cursor, Continue.dev, Cline, the MetaMCP aggregator on edge-host) | MCP tools via stdio | `/path/to/rote/mcp-server/start.sh` |
| Any function-calling LLM (OpenAI-compatible APIs, local Ollama, sglang) | OpenAPI spec | `http://127.0.0.1:5572/openapi.json` |

All three share the same SQLite DB, vault, and delegate registry — the source of truth lives in the FastAPI server. Connecting from Claude Desktop / Cursor / etc.: see `/path/to/rote/mcp-server/README.md`.

## Cross-reference

- [[secret-handling]] — secret-specific use cases (vault, .env injection)
- [[chronicle]] — session post-mortem — should automatically record new anti-patterns
- [[local-delegate]] — sibling skill for deferring work to the delegate registry

## Recovery if the API is down

```bash
rote up
# polls healthz for 30s; reports up/timeout

# manual:
/path/to/rote/server/start.sh
```

Server logs at `/path/to/rote/server/data/server.log`. State at `/path/to/rote/server/data/audit.sqlite`.
