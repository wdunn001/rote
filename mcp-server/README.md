# Rote MCP Server

A thin MCP adapter that exposes the local Rote HTTP API as MCP tools, so any MCP-compatible LLM client can use the discovery/vault/delegate/anti-pattern surface natively.

## Why both an HTTP API and an MCP server?

| Path | Used by |
|---|---|
| **HTTP API** at `127.0.0.1:5572` (FastAPI, OpenAPI auto-docs at `/docs`) | Function-calling LLMs (any OpenAI-compatible API; pass the OpenAPI spec). Bash scripts. The CLI `rote`. The GUI. |
| **MCP server** (this directory) | MCP-protocol clients: Claude Desktop, Cursor, Continue.dev, Cline, JetBrains AI Assistant, the MetaMCP aggregator on edge-host. |

Same backend, same data, two protocols. Both stay in sync because both call the same FastAPI server.

## Tools exposed

The full list — every tool the MCP client will see:

### Script discovery + execution
- `find_script(query, limit?)` — semantic search
- `list_scripts()` — full inventory
- `show_script(name)` — frontmatter of one
- `run_script(name, args?, timeout_seconds?)` — execute, capture stdout/stderr/exit

### Vault (NAMES only — values never returned)
- `vault_keys()` — names + byte sizes
- `vault_has(keys)` — which exist
- `vault_inject(env_file, keys, block_label?)` — write secrets into a .env, server-side

### Anti-patterns
- `find_anti_pattern(query, limit?)` — semantic search
- `list_anti_patterns()` — sorted by hit count
- `add_anti_pattern(slug, title, symptom, remedy, token_cost?)` — record or bump

### Delegates (defer mechanical work to local resources)
- `list_delegates()` — registered local LLMs / MCP servers / SSH hosts
- `best_delegate(capability, min_attempts?, min_success_rate?)` — pick the proven-best
- `show_delegate(name)` — full record + recent log
- `dispatch_to_delegate(delegate, capability, prompt, …)` — defer to an LLM delegate
- `dispatch_mcp_tool(delegate, tool_name, args, …)` — call an MCP tool via MetaMCP
- `log_delegation(delegate, capability, task_summary, outcome, …)` — record outcome
- `add_delegate(name, kind, contact, capabilities, …)` — register a new resource

### Diagnostics
- `healthz()` — backend health
- `recent_audit(limit?)` — audit events (key names + counts, never bytes)

## Setup (first time)

```bash
# from anywhere
~/.claude/rote/mcp-server/start.sh
```

First run bootstraps a venv at `~/.cache/rote-mcp/venv/` (WSL native, not drvfs — much faster, no fragility) and installs `mcp` + `httpx`. Subsequent runs just exec the server.

Idempotent. Safe to invoke from any MCP client config.

## Connecting an MCP client

The MCP server is launched as a subprocess by the client. Each client has its own config file.

### Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "rote": {
      "command": "/path/to/rote/mcp-server/start.sh",
      "env": {
        "SCRIPT_LIBRARY_API": "http://127.0.0.1:5572"
      }
    }
  }
}
```

Restart Claude Desktop. Tools should appear in the conversation surface.

### Cursor

`~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "rote": {
      "command": "/path/to/rote/mcp-server/start.sh"
    }
  }
}
```

### Continue.dev

`~/.continue/config.yaml`:

```yaml
mcpServers:
  - name: rote
    command: /path/to/rote/mcp-server/start.sh
```

### Cline (VS Code extension)

VS Code settings — `cline.mcp.servers`:

```json
{
  "rote": {
    "command": "/path/to/rote/mcp-server/start.sh"
  }
}
```

### Any MCP client

Generic pattern:
- **command**: `/path/to/rote/mcp-server/start.sh`
- **transport**: stdio (default for command-launched servers)
- **env**: optionally set `SCRIPT_LIBRARY_API` to point at a different backend

## Registering with MetaMCP (edge-host)

Once the rote MCP server is reachable from edge-host, register it in MetaMCP so OTHER LLMs going through the MetaMCP aggregator inherit access:

1. Log into the MetaMCP admin UI at `http://edge-host:12008`
2. Add a new MCP server with:
   - **Type**: command / stdio
   - **Command**: `/path/to/rote/mcp-server/start.sh` (path on the edge-host box if you mirror the repo there, OR run the rote on edge-host directly)
   - **Env**: `SCRIPT_LIBRARY_API=http://localhost:5572`
3. Attach to an existing namespace or create one (e.g. `mz-dev`)
4. Any LLM client routed through that MetaMCP endpoint now gets rote tools

Caveat: the rote backend (FastAPI + SQLite + vault) currently runs on the WSL box, not edge-host. To run it from edge-host you'd either:
- Mirror the repo + state to edge-host and let it own the data
- Point the MCP server's `SCRIPT_LIBRARY_API` at the WSL box (will need the WSL API to listen on `0.0.0.0` or a tunnel — **adds auth requirement** because vault endpoints currently trust localhost)

The cleaner long-term move is one canonical rote backend with proper auth; that's a roadmap item (see [`../ROADMAP.md`](../ROADMAP.md#backlog) — "Authn for non-localhost API access").

## Troubleshooting

**MCP client says "server not responding":**
- `~/.claude/rote/mcp-server/start.sh < /dev/null` — should exit with an MCP handshake error to stderr, confirming the binary works.
- Make sure the FastAPI backend is up: `curl -fsS http://127.0.0.1:5572/healthz`.
- Check the client's MCP log for the captured stderr — `mcp/start.sh` writes install + error diagnostics there.

**`mcp` import fails:**
- venv install was interrupted. Wipe + retry: `rm -rf ~/.cache/rote-mcp/venv && ~/.claude/rote/mcp-server/start.sh < /dev/null`.

**`vault_keys` doesn't return values:**
- That's intentional and binding. Use `vault_inject` to land values in a `.env` server-side.
