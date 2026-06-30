#!/usr/bin/env bash
# =============================================================================
# script: bootstrap-context-system.sh
# purpose: Fresh-machine bootstrap.  Runs every step needed to take a clean
#          git clone of rote to "ready" state: backend venv +
#          API up, MCP venv ready, MCP client configs written, end-to-end
#          smoke test green.  Idempotent — re-runs are safe.
# inputs:
#   --skip-clients      don't write MCP client configs (e.g. headless server)
#   --no-verify         skip the smoke test at the end
#   --api-port <int>    override default 5572
#   --wait-timeout <s>  how long to wait for API binding (default 600 = 10 min
#                       to accommodate cold-start sentence-transformers download)
# outputs:
#   stdout: progress per stage
#   exit 0 ready, non-zero on any stage failure
# touches-secrets: no
# when-to-use:    fresh clone on a new machine; first run of the day; after a
#                 venv reset; demo-readiness check before a session
# when-NOT-to-use: when the system is up + verified — this is the slow path
# added: 2026-06-03
# family: bootstrap-context-system
# environment: posix-bash
# =============================================================================
set -uo pipefail

REPO_DIR="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
API_PORT="5572"
SKIP_CLIENTS=0
NO_VERIFY=0
WAIT_TIMEOUT=600

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-clients)  SKIP_CLIENTS=1; shift ;;
        --no-verify)     NO_VERIFY=1; shift ;;
        --api-port)      API_PORT="$2"; shift 2 ;;
        --wait-timeout)  WAIT_TIMEOUT="$2"; shift 2 ;;
        -h|--help)       sed -n '3,22p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 5 ;;
    esac
done

API="http://127.0.0.1:${API_PORT}"

step()    { echo; echo "=== [$1/$2] $3 ==="; }
ok()      { echo "  [ok] $*"; }
fail()    { echo "  [FAIL] $*" >&2; exit 1; }
note()    { echo "  $*"; }

echo "Rote bootstrap"
echo "  repo: $REPO_DIR"
echo "  api : $API"
echo "  wait: ${WAIT_TIMEOUT}s for API binding"

# -----------------------------------------------------------------------------
# 1. Backend venv + server up
# -----------------------------------------------------------------------------
step 1 5 "backend up + binding"

# If something's already bound on the port, see if it's ours.
if curl -fsS -m 2 "$API/healthz" >/dev/null 2>&1; then
    ok "API already responding"
else
    note "starting backend in background ($REPO_DIR/server/start.sh)"
    nohup "$REPO_DIR/server/start.sh" \
        >> "$REPO_DIR/server/data/server.log" 2>&1 </dev/null &
    disown 2>/dev/null || true
    note "polling /healthz for up to ${WAIT_TIMEOUT}s"
    DEADLINE=$(( $(date +%s) + WAIT_TIMEOUT ))
    while ! curl -fsS -m 1 "$API/healthz" >/dev/null 2>&1; do
        if [[ $(date +%s) -gt "$DEADLINE" ]]; then
            fail "API did not bind within ${WAIT_TIMEOUT}s — check $REPO_DIR/server/data/server.log"
        fi
        sleep 5
    done
    ok "API responding"
fi

# -----------------------------------------------------------------------------
# 2. MCP server venv bootstrap (don't start; the client launches it)
# -----------------------------------------------------------------------------
step 2 5 "MCP server venv"

MCP_VENV="$HOME/.cache/rote-mcp/venv"
if [[ -x "$MCP_VENV/bin/python" ]] && "$MCP_VENV/bin/python" -c "import mcp, httpx" 2>/dev/null; then
    ok "MCP venv already populated"
else
    note "running $REPO_DIR/mcp-server/start.sh with stdin closed so it bootstraps then exits cleanly"
    # The MCP server runs forever waiting for stdio; we just need the venv
    # bootstrap.  Close stdin and timeout after the install completes — pip
    # finishing is the gate.
    timeout 600 bash -c "$REPO_DIR/mcp-server/start.sh < /dev/null" 2>&1 | tail -5 || true
    if [[ -x "$MCP_VENV/bin/python" ]] && "$MCP_VENV/bin/python" -c "import mcp, httpx" 2>/dev/null; then
        ok "MCP venv bootstrapped"
    else
        fail "MCP venv missing mcp / httpx after bootstrap attempt — see $REPO_DIR/mcp-server/.venv"
    fi
fi

# -----------------------------------------------------------------------------
# 3. MCP client configs
# -----------------------------------------------------------------------------
step 3 5 "MCP client configs"

if [[ "$SKIP_CLIENTS" -eq 1 ]]; then
    note "--skip-clients set; not writing config files"
else
    "$REPO_DIR/scripts/install-mcp-client-config.sh" \
        --command "$REPO_DIR/mcp-server/start.sh" \
        --api "$API" || note "(installer reported a partial result — check output above)"
fi

# -----------------------------------------------------------------------------
# 4. Claude Code skills + memory entry
# -----------------------------------------------------------------------------
step 4 5 "Claude Code skills install"

ANY_MISSING=0
for skill in rote secret-handling chronicle local-delegate; do
    [[ -f "$HOME/.claude/skills/$skill/SKILL.md" ]] || ANY_MISSING=1
done

if [[ "$ANY_MISSING" -eq 1 ]]; then
    note "skills missing under ~/.claude/skills/ — installing from $REPO_DIR/claude-code-skills/"
    "$REPO_DIR/scripts/install-claude-code-skills.sh" || \
        fail "claude code skills install reported errors"
else
    note "all four skills already present; running install with --no-backup to refresh"
    "$REPO_DIR/scripts/install-claude-code-skills.sh" --no-backup || note "(skills refresh reported a partial result)"
fi
ok "skills installed"

# -----------------------------------------------------------------------------
# 5. End-to-end verification
# -----------------------------------------------------------------------------
step 5 5 "end-to-end verification"

if [[ "$NO_VERIFY" -eq 1 ]]; then
    note "--no-verify set; skipping smoke test"
else
    "$REPO_DIR/scripts/verify-context-system.sh" --api "$API" || \
        fail "verification reported issues — see above"
    ok "verification clean"
fi

echo
echo "=== Bootstrap complete ==="
echo "  CLI : $REPO_DIR/cli/rote find '<query>'"
echo "  GUI : $API/"
echo "  MCP : registered with your client(s); restart the client to load tools"
exit 0
