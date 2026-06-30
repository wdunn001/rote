#!/usr/bin/env bash
# =============================================================================
# script: dispatch-to-metamcp.sh
# purpose: Call an MCP tool through the MetaMCP aggregator on edge-host.  Reads the
#          API key out of the local vault (never echoes it; never enters
#          Claude's context) and runs the MCP protocol handshake → tools/call.
#          Logs the outcome to the delegations table.
#
# **Auth flow (binding):** the Bearer token comes from the vault via the
# Rote API.  This script does NOT accept the token on the command
# line — that would put the value in shell history and possibly in tool-call
# transcripts.  If the vault is missing the key, the script exits 4 with a
# clear "ask the user to populate METAMCP_API_KEY" message.
#
# inputs:
#   --endpoint <name>      MetaMCP endpoint name (default: openwebui-api)
#   --tool <name>          tool to call (required)
#   --args <json>          tool arguments as JSON (default: {})
#                          Pass @path to read JSON from a file.
#   --delegate <name>      delegate row (default: metamcp-delegate)
#   --capability <tag>     capability tag for logging (default: mcp-tool-aggregation)
#   --vault-key <name>     vault key holding the bearer (default: METAMCP_API_KEY)
#   --task <text>          short summary recorded in the delegation_log
#   --estimated-saved <n>  estimated Claude tokens NOT spent
#   --no-log               skip the delegation_log POST
#   --api <url>            override Rote API base (default 127.0.0.1:5572)
#   --raw                  emit the raw MCP-protocol response instead of the result body
# outputs:
#   stdout: the tool's result.content body (or raw with --raw)
#   stderr: latency + (on failure) error message
#   exit 0 success, 3 tool returned an error, 4 unreachable / auth missing,
#         5 bad args, 6 logging failed (response still printed)
# touches-secrets: yes (reads bearer from vault; never prints it)
# when-to-use:    discovering or invoking any MCP tool MetaMCP aggregates
# when-NOT-to-use: tasks the Ollama or sglang delegates handle (plain LLM work)
# added: 2026-06-03
# family: dispatch-to-metamcp
# environment: posix-bash
# =============================================================================
set -euo pipefail

ENDPOINT="openwebui-api"
TOOL=""
ARGS_JSON='{}'
DELEGATE="metamcp-delegate"
CAPABILITY="mcp-tool-aggregation"
VAULT_KEY="METAMCP_API_KEY"
TASK=""
ESTIMATED_SAVED=""
NO_LOG=0
RAW=0
API="${API:-http://127.0.0.1:5572}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --endpoint)        ENDPOINT="$2"; shift 2 ;;
        --tool)            TOOL="$2"; shift 2 ;;
        --args)            ARGS_JSON="$2"; shift 2 ;;
        --delegate)        DELEGATE="$2"; shift 2 ;;
        --capability)      CAPABILITY="$2"; shift 2 ;;
        --vault-key)       VAULT_KEY="$2"; shift 2 ;;
        --task)            TASK="$2"; shift 2 ;;
        --estimated-saved) ESTIMATED_SAVED="$2"; shift 2 ;;
        --no-log)          NO_LOG=1; shift ;;
        --raw)             RAW=1; shift ;;
        --api)             API="$2"; shift 2 ;;
        -h|--help)         sed -n '3,38p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 5 ;;
    esac
done

[[ -n "$TOOL" ]] || { echo "--tool required" >&2; exit 5; }

command -v curl >/dev/null || { echo "curl required" >&2; exit 5; }
command -v jq   >/dev/null || { echo "jq required"   >&2; exit 5; }

# Allow @path for the args JSON.
if [[ "${ARGS_JSON:0:1}" == "@" ]]; then
    ARGS_PATH="${ARGS_JSON:1}"
    [[ -r "$ARGS_PATH" ]] || { echo "unreadable args file: $ARGS_PATH" >&2; exit 5; }
    ARGS_JSON=$(cat "$ARGS_PATH")
fi
echo "$ARGS_JSON" | jq -e . >/dev/null 2>&1 || { echo "--args must be valid JSON" >&2; exit 5; }

log_outcome() {
    local outcome="$1" latency="$2" notes="${3:-}"
    local body
    body=$(jq -nc \
        --arg d "$DELEGATE" --arg c "$CAPABILITY" \
        --arg t "${TASK:-tool=${TOOL} endpoint=${ENDPOINT}}" --arg o "$outcome" \
        --arg n "$notes" \
        --argjson lat "$latency" \
        --argjson sv "${ESTIMATED_SAVED:-null}" \
        '{delegate:$d, capability:$c, task_summary:$t, outcome:$o,
          latency_ms:$lat, token_savings:$sv, notes:$n}')
    curl -fsS -X POST -H "Content-Type: application/json" \
        --data "$body" "$API/delegations" >/dev/null
}

# Resolve delegate URL.
URL=$(curl -fsS "$API/delegates/$DELEGATE" 2>/dev/null | jq -r '.contact.url // empty')
if [[ -z "$URL" ]]; then
    echo "could not resolve delegate $DELEGATE via $API" >&2
    exit 4
fi
MCP_URL="${URL%/}/metamcp/${ENDPOINT}/mcp"

# Read the bearer from the local vault.  Local filesystem, same trust
# boundary as the API process — bytes never enter Claude's context because
# this script's stdout/stderr never echo the value.  Unset on exit so the
# value doesn't linger in the environment of any child process.
trap 'unset BEARER' EXIT
VAULT_PATH=$(curl -fsS "$API/vault/keys" 2>/dev/null | jq -r '.vault_path // empty')
[[ -n "$VAULT_PATH" ]] || VAULT_PATH="/path/to/rote/secret-vault/secrets.json"
BEARER=$(VAULT_PATH="$VAULT_PATH" VAULT_KEY="$VAULT_KEY" python3 -c '
import json, os, pathlib, sys
p = pathlib.Path(os.environ["VAULT_PATH"])
if not p.exists(): sys.exit(0)
d = json.loads(p.read_text())
sys.stdout.write(d.get(os.environ["VAULT_KEY"], ""))
' 2>/dev/null) || true

if [[ -z "$BEARER" ]]; then
    echo "vault has no '$VAULT_KEY' — populate it before calling MetaMCP" >&2
    echo "  vault path: $VAULT_PATH" >&2
    echo "  see: ~/.claude/skills/secret-handling/SKILL.md (Adding a secret)" >&2
    exit 4
fi

HEADERS_AUTH="Authorization: Bearer $BEARER"
HEADERS_ACCEPT='Accept: application/json, text/event-stream'

# Time the whole handshake + call.
START_MS=$(date +%s%3N)

# Step 1: initialize.  MCP protocol requires this before any tool call.
INIT_BODY=$(jq -nc '{
    jsonrpc:"2.0", id:1, method:"initialize",
    params:{
        protocolVersion:"2024-11-05",
        clientInfo:{name:"dispatch-to-metamcp.sh", version:"0.1"},
        capabilities:{}
    }
}')
INIT_RESPONSE=$(curl -fsS -X POST \
    -H "$HEADERS_AUTH" -H "$HEADERS_ACCEPT" -H "Content-Type: application/json" \
    --data "$INIT_BODY" "$MCP_URL" 2>&1) || {
    LATENCY_MS=$(( $(date +%s%3N) - START_MS ))
    echo "initialize failed (latency=${LATENCY_MS}ms): $INIT_RESPONSE" >&2
    if [[ "$NO_LOG" -eq 0 ]]; then
        log_outcome "failure" "$LATENCY_MS" "initialize failed" || true
    fi
    exit 4
}

# MetaMCP streams responses as SSE on this endpoint.  Find the JSON line in
# the SSE stream.  If it's a single JSON object response, jq -e succeeds on it.
parse_sse_or_json() {
    local raw="$1"
    if echo "$raw" | jq -e . >/dev/null 2>&1; then
        echo "$raw"
    else
        # SSE: lines like 'data: {...}'.  Concatenate JSON content.
        echo "$raw" | sed -n 's/^data: //p' | head -1
    fi
}

INIT_PARSED=$(parse_sse_or_json "$INIT_RESPONSE")

# Some MetaMCP versions return a session id we must pass on subsequent
# requests.  Look for `Mcp-Session-Id` header — but `curl -fsS` swallows
# headers.  Repeat the call with --dump-header if needed; for now, attempt
# without and rely on the JSON-RPC `id` correlation.

# Step 2: tools/call.
CALL_BODY=$(jq -nc --arg tool "$TOOL" --argjson args "$ARGS_JSON" '{
    jsonrpc:"2.0", id:2, method:"tools/call",
    params:{name:$tool, arguments:$args}
}')
CALL_RESPONSE=$(curl -fsS -X POST \
    -H "$HEADERS_AUTH" -H "$HEADERS_ACCEPT" -H "Content-Type: application/json" \
    --data "$CALL_BODY" "$MCP_URL" 2>&1) || {
    LATENCY_MS=$(( $(date +%s%3N) - START_MS ))
    echo "tools/call failed (latency=${LATENCY_MS}ms): $CALL_RESPONSE" >&2
    if [[ "$NO_LOG" -eq 0 ]]; then
        log_outcome "failure" "$LATENCY_MS" "tools/call failed" || true
    fi
    exit 4
}

LATENCY_MS=$(( $(date +%s%3N) - START_MS ))

CALL_PARSED=$(parse_sse_or_json "$CALL_RESPONSE")

# Did MCP return an error?
MCP_ERROR=$(echo "$CALL_PARSED" | jq -r '.error.message // empty' 2>/dev/null)
if [[ -n "$MCP_ERROR" ]]; then
    echo "tool returned MCP error (latency=${LATENCY_MS}ms): $MCP_ERROR" >&2
    if [[ "$NO_LOG" -eq 0 ]]; then
        log_outcome "failure" "$LATENCY_MS" "mcp error: ${MCP_ERROR:0:200}" || true
    fi
    exit 3
fi

if [[ "$RAW" -eq 1 ]]; then
    echo "$CALL_PARSED"
else
    # Tool results live under .result.content; render as text or JSON.
    echo "$CALL_PARSED" | jq -r '.result.content[]?.text // .result.content[]? // .result // .'
fi

echo "[ok] ${DELEGATE} ${CAPABILITY} ${TOOL} ${LATENCY_MS}ms" >&2

if [[ "$NO_LOG" -eq 0 ]]; then
    log_outcome "success" "$LATENCY_MS" "" || {
        echo "[warn] logging failed (response printed above)" >&2
        exit 6
    }
fi
