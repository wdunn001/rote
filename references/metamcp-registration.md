# Registering the rote MCP server with MetaMCP (edge-host)

MetaMCP on edge-host aggregates downstream MCP servers and presents them as a single endpoint that any MCP-aware LLM can connect to. Registering the rote MCP server with MetaMCP is how every LLM going through MetaMCP — including local LLMs on edge-host itself — inherits the rote's discovery, vault, and delegate tools without per-client config.

## Current state (2026-06-03)

- MetaMCP: `http://edge-host:12008` (edge-host), auth via `METAMCP_API_KEY` (in the local vault).
- Known endpoint: `openwebui-api` — the namespace OpenWebUI connects through.
- Rote backend: lives on the WSL box (`127.0.0.1:5572`). The rote MCP server (`mcp-server/start.sh`) wraps it.

## The architectural choice

The MCP server needs network access to the rote FastAPI backend. Two options:

### Option A: Run the rote MCP server ON edge-host (recommended)

Mirror the repo to edge-host, run a co-located rote backend there, register the local MCP server with MetaMCP. All loopback; no cross-machine auth needed.

### Option B: Keep the backend on WSL, register a remote-pointing MCP server

The MCP server runs on edge-host but points at `http://wsl-host-ip:5572`. Requires the WSL API to listen on `0.0.0.0` AND to gain auth (see ROADMAP #7), so this is the "later" path.

The rest of this doc assumes Option A.

## Option A walkthrough

### 1. Mirror the rote to edge-host

From the WSL box:

```bash
ssh user@edge-host 'mkdir -p /home/edge-host/rote'
rsync -avz --exclude='server/.venv' --exclude='mcp-server/.venv' \
    --exclude='server/data/audit.sqlite*' --exclude='secret-vault/secrets.json' \
    /path/to/rote/ user@edge-host:/home/edge-host/rote/
```

The exclude list keeps the venv (rebuilt on edge-host) + secrets + state local. Each machine has its own audit DB and vault; that's intentional.

### 2. Populate edge-host's vault with whatever secrets it needs

The edge-host instance is now a separate context. If the LLMs on edge-host will dispatch to MetaMCP they need `METAMCP_API_KEY`, etc. The user adds these out-of-band by editing `/home/edge-host/rote/secret-vault/secrets.json` directly (file mode 0600 on edge-host's ext4 — actually enforced).

### 3. Bootstrap on edge-host

```bash
ssh user@edge-host
cd /home/edge-host/rote
./server/start.sh   # backgroun this; ctrl-z + bg, or tmux/systemd
```

First run installs the venv + sentence-transformers (~3 min on edge-host's faster CPU).

### 4. Register with MetaMCP

MetaMCP admin UI lives at `http://edge-host:12008`. Walk through:

1. Log in. (If the password isn't in the vault, retrieve it from wherever the user keeps the master MetaMCP admin creds.)
2. Navigate to **MCP Servers** → **New Server**.
3. Fill in:
   - **Name:** `rote`
   - **Type:** `STDIO` (subprocess pattern)
   - **Command:** `/home/edge-host/rote/mcp-server/start.sh`
   - **Args:** (none)
   - **Env:**
     - `SCRIPT_LIBRARY_API` = `http://127.0.0.1:5572`
4. Save. MetaMCP will spawn a subprocess on the first incoming request from any client.
5. Navigate to **Namespaces** → pick or create the namespace whose endpoint should inherit the rote tools (e.g. `mz-dev` or extend `openwebui-api`).
6. Attach the `rote` MCP server to that namespace.

Any LLM client connecting through `http://edge-host:12008/metamcp/<namespace>/mcp` now gets the 17 rote tools alongside whatever other tools MetaMCP aggregates for that namespace.

### 5. Verify from the WSL side

```bash
# Pull namespace tools via MetaMCP and grep for rote names.
/path/to/rote/scripts/dispatch-to-metamcp.sh \
    --tool list_scripts \
    --args '{}' \
    --endpoint mz-dev \
    --task "verify rote aggregated via MetaMCP" \
    --no-log
```

If the call succeeds and returns a script list, the loop is closed. The same call goes:

```
WSL Claude Code
  → dispatch-to-metamcp.sh
    → POST http://edge-host:12008/metamcp/mz-dev/mcp (Bearer from vault)
      → MetaMCP routes to its `rote` subprocess
        → MCP server forwards to http://127.0.0.1:5572 (on edge-host)
          → FastAPI returns rote data
        → MCP response
      → MetaMCP wraps response
    → dispatch script prints to stdout
  → Claude reads stdout
```

## Synchronizing the two instances

Now there are two rote instances (one on WSL, one on edge-host). The bash scripts at `scripts/dispatch-*.sh` and the markdown anti-patterns live in git, so `git pull` on edge-host gets them. The state that differs by design:

| Per-instance state | Sync strategy |
|---|---|
| `server/data/audit.sqlite` | None — each instance owns its own log. Optional: periodic merge if you want one unified view. |
| `secret-vault/secrets.json` | None — each instance trusts its own host. Don't sync. |
| `delegations log` | Per-instance, so calibration runs against the WSL backend show in WSL stats, edge-host-side runs show in edge-host stats. |
| Custom scripts the user adds | `git push` from one + `git pull` on the other. |
| Anti-patterns added during a session | Same — both `chronicle add-anti-pattern` calls flow to `git add` + `git push`. |

The "two instances, one source of truth" pattern is intentional. Anything that should be shared lives in git. Anything that's local context (audit, vault, log) stays local.

## When NOT to register with MetaMCP

If the LLMs you're using are exclusively MCP-aware clients on the WSL host (Claude Desktop on Windows, Cursor on the same machine), skip MetaMCP and point them at the WSL `mcp-server/start.sh` directly. MetaMCP earns its keep when you have multiple LLM clients OR LLMs that aren't MCP-aware (and rely on MetaMCP's tool-aggregation surface).

## Troubleshooting

**`dispatch-to-metamcp.sh` returns "Server not initialized":**
- MetaMCP requires the MCP `initialize` handshake before `tools/call`. The dispatcher already does this — if you see this error it usually means MetaMCP's namespace was attached but the subprocess hasn't been warmed yet. Make a `list_scripts` call to warm it.

**MetaMCP subprocess crashes on first dispatch:**
- Check MetaMCP's logs (`docker logs metamcp --tail 50`) for the actual error.
- Most common: the rote backend on edge-host isn't running. Start it: `ssh user@edge-host 'cd /home/edge-host/rote && nohup ./server/start.sh >> server/data/server.log 2>&1 &'`.

**Bearer 401 errors:**
- The `METAMCP_API_KEY` in your local vault is the right key for the WSL-side dispatcher to AUTHENTICATE TO MetaMCP. The dispatcher reads it via `dispatch-to-metamcp.sh`'s vault-read path. If the key has been rotated, update the vault.
