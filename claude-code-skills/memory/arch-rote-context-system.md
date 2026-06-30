---
name: arch-rote-context-system
description: Rote — a local persistent context system (FastAPI + sqlite-vec semantic search + vault + delegate registry + MCP server + 5 Claude skills). Use before writing shell, designing pattern-shaped code, or deferring bulk work.
metadata:
  node_type: memory
  type: project
---

Rote is a local persistent context system installed on this machine. It gives an agent a memory of the deterministic things already solved, so it recalls a proven tool instead of regenerating one.

- **Repo:** https://github.com/wdunn001/rote
- **Backend:** FastAPI on `127.0.0.1:5572`
- **Database:** `server/data/audit.sqlite` (sqlite + sqlite-vec); a CACHE of the file-backed catalogs, not the source of truth
- **Vault:** `secret-vault/secrets.json` (gitignored; secret BYTES never enter the model context)

**Why:** Before writing a new shell script for a recurring operation, before designing pattern-shaped code, before reading 5+ KB of logs to summarize, before writing a secret value into a `.env`, before recording a bug pattern that bit a session, check here. The library is deterministic, auditable, and known-cost; the model regenerating the same thing twice is wasteful, unsafe, or both.

**Companion skills** (`~/.claude/skills/`):
- `rote` — discovery + execution + the "library first" hard rules
- `design-patterns` — search pattern/tech/snippet/stack catalogs before designing
- `secret-handling` — vault routing; never put secret values in tool calls
- `local-delegate` — defer mechanical bulk work to compute you own
- `chronicle` — session post-mortem; records findings back into the catalogs

**Four surfaces** to the same backend: CLI (`cli/rote`), GUI (`http://127.0.0.1:5572/`), MCP (`mcp-server/start.sh`), OpenAPI (`http://127.0.0.1:5572/openapi.json`).

**How to apply:** When you'd normally write `bash -c "..."` for a multi-step op, first try `rote find "<one-line description>"`. When you'd normally read a big log to summarize, try `rote delegate best bulk-summarization` then dispatch. When you'd normally hand-roll a known design pattern, try `rote dp find "<intent>"`.

**Bootstrap:** `./server/start.sh` (one-time ~3 min for venv + 80 MB embedding model). Runs fully self-contained — no external services required. `./scripts/verify-context-system.sh` confirms readiness.
