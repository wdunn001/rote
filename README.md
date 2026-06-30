# Rote

**Stop letting your AI reinvent the wheel.** Rote is a small local server that gives an AI agent a memory of the deterministic things you have already solved: reusable scripts, code snippets, design patterns, shell commands, prompts, and the anti-patterns to avoid. The agent searches the library first (full-text and semantic) and calls the proven, auditable tool instead of regenerating it from scratch and gambling on the result.

> A skill is a prompt. A recalled tool is a guarantee. Skills do not solve problems; skills backed by deterministic solutions do.

It is, honestly, just RAG. The point is how little you need for it to pay off: one SQLite file, a few hundred lines of FastAPI, and the discipline of writing a reusable thing down once instead of having the model roll its own every time. It runs fully self-contained with no external services.

## What's in the box

- **FastAPI backend** at `127.0.0.1:5572` with [sqlite-vec](https://github.com/asg017/sqlite-vec) semantic search over every catalog
- **CLI** (`cli/rote`) — tab-separated output for token-efficient access from an agent
- **GUI** at `GET /` — single-page explorer for humans (vanilla HTML, no framework, no CDN)
- **MCP server** ([`mcp-server/`](./mcp-server/)) — tools for Claude Desktop, Claude Code, Cursor, Continue.dev, Cline, and MCP aggregators
- **OpenAPI spec** at `/openapi.json` for function-calling LLMs (Anthropic API, OpenAI, Gemini, local Ollama/sglang)
- **Catalogs** — `scripts/`, `snippets/`, `design-patterns/`, `technologies/`, `commands/`, `prompts/`, `stacks/`, `anti-patterns/`, all file-backed markdown, auto-indexed by mtime
- **Vault** — secret bytes stay server-side; the model knows secret NAMES only
- **Delegates registry** — track local compute you own + per-capability success rate so the agent knows what bulk work to defer off the expensive model
- **Claude Code skills** — five skills that wire an agent to all of the above

## Why "library before LLM"

Every catalog entry is a plain file with frontmatter. The SQLite database is a **cache, not the source of truth** — you edit files, the server reindexes on the next list/search by comparing mtimes. Search has two modes: keyed/full-text filters (`GET /scripts?family=...`) and semantic KNN (`POST /scripts/search` embeds the query and ranks by cosine distance). When the closest hit is good enough, the agent runs the recalled artifact instead of generating one. That is the whole idea.

## Quick start

```bash
git clone https://github.com/wdunn001/rote.git
cd rote
./server/start.sh        # first run builds a venv + downloads the embedding model (~80 MB), then binds 127.0.0.1:5572
```

By default Rote embeds locally with `all-MiniLM-L6-v2` (384-dim) — **no Ollama, no API key, nothing external required.** To offload embeddings to an Ollama endpoint you own, export `OLLAMA_EMBED_URL=http://localhost:11434` before starting.

Then, from another shell:

```bash
./cli/rote up                       # start the server in the background if it isn't already
./cli/rote find "inject env secrets"   # semantic search the script catalog
./cli/rote dp find "safe retry of a flaky remote call"   # search design patterns
./cli/rote ap find "committing secrets to .env"          # search anti-patterns
./cli/rote delegate list            # registered local compute + per-capability stats
./cli/rote verify                   # end-to-end smoke test
open http://127.0.0.1:5572/         # the GUI
```

## Connecting agents

| Client | Install command |
|---|---|
| **Claude Code (CLI)** | `./cli/rote skills-install` — installs the five skills + memory entry under `~/.claude/` |
| Claude Desktop, Cursor, Continue.dev, Cline | `./cli/rote mcp-install` — auto-detects and writes MCP configs |
| MCP aggregator (e.g. MetaMCP) | [`references/metamcp-registration.md`](./references/metamcp-registration.md) |
| Anthropic API / OpenAI / Gemini / Ollama / sglang | [`references/openapi-integration.md`](./references/openapi-integration.md) |

## Claude Code skills

The five skills live at [`claude-code-skills/`](./claude-code-skills/) and install to `~/.claude/skills/<name>/SKILL.md`.

- `rote` — discovery + execution + the "library first" hard rules
- `design-patterns` — search the pattern/tech/snippet/stack catalogs before designing pattern-shaped code
- `secret-handling` — the vault flow; never put secret values in tool calls
- `local-delegate` — defer mechanical bulk work to the delegate registry
- `chronicle` — session post-mortem; records findings back into the catalogs

## The codec-web example

[`examples/codec-web/`](./examples/codec-web/) is a runnable demo of Rote as the local switchboard behind a cloud coordinator: it runs a **doomed-prompt pre-check locally** (rejecting malformed prompts before they cost a remote round-trip), **injects a secret from the client-side vault locally** (so the secret bytes never reach the remote model), and only then dispatches the bulk work to a delegate you own. See its README for the why.

## Documentation

- [`server/README.md`](./server/README.md) — endpoint table + data model + operational notes
- [`mcp-server/README.md`](./mcp-server/README.md) — MCP tool list + per-client setup
- [`references/openapi-integration.md`](./references/openapi-integration.md) — non-MCP function-calling integration
- [`claude-code-skills/README.md`](./claude-code-skills/README.md) — skill install + maintainer workflow

## License

MIT — see [LICENSE](./LICENSE).
