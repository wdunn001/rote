#!/usr/bin/env bash
# =============================================================================
# script: dispatch-to-ollama.sh
# purpose: Send a prompt to an Ollama delegate, print the response to stdout,
#          auto-log the outcome (latency + token-savings estimate) to the
#          delegations table.  Closes the "best→defer→log" loop so Claude can
#          defer mechanical work in one shell call.
# inputs:
#   --delegate <name>      delegate row name (default: local-llm)
#   --capability <tag>     capability tag for logging (default: bulk-summarization)
#   --model <name>         Ollama model (default: qwen2.5:latest)
#   --prompt <text>        prompt text (mutually exclusive with --prompt-file / stdin)
#   --prompt-file <path>   read prompt from file
#   --system <text>        optional system prompt
#   --temperature <float>  default 0.2 (deterministic-leaning)
#   --max-tokens <int>     default 2048
#   --task <text>          short summary recorded in the delegation_log
#   --estimated-saved <n>  estimated Claude output tokens NOT spent (best-effort)
#   --no-log               skip the delegation_log POST (use during dry runs)
#   --api <url>            override Rote API base (default 127.0.0.1:5572)
#   --raw                  emit the raw JSON Ollama response instead of just the text
# outputs:
#   stdout: the assistant's reply text (or raw JSON with --raw)
#   stderr: latency + (on failure) error message
#   exit 0 success, 3 delegate returned empty, 4 API/delegate unreachable,
#         5 bad args, 6 logging failed (response still printed)
# touches-secrets: no (no auth on Ollama LAN endpoint per the registry)
# when-to-use:    bulk-summarization, log-skim, doc-skim, yes/no-classification,
#                 code-snippet-extraction, embedding (use --task to disambiguate)
# when-NOT-to-use: tasks requiring Claude's reasoning, voice, or session context
# added: 2026-06-03
# family: dispatch-to-ollama
# environment: posix-bash
# =============================================================================
set -euo pipefail

DELEGATE="local-llm"
CAPABILITY="bulk-summarization"
MODEL="qwen2.5:latest"
PROMPT=""
PROMPT_FILE=""
SYSTEM=""
TEMPERATURE="0.2"
MAX_TOKENS="2048"
TASK=""
ESTIMATED_SAVED=""
NO_LOG=0
RAW=0
API="${API:-http://127.0.0.1:5572}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --delegate)        DELEGATE="$2"; shift 2 ;;
        --capability)      CAPABILITY="$2"; shift 2 ;;
        --model)           MODEL="$2"; shift 2 ;;
        --prompt)          PROMPT="$2"; shift 2 ;;
        --prompt-file)     PROMPT_FILE="$2"; shift 2 ;;
        --system)          SYSTEM="$2"; shift 2 ;;
        --temperature)     TEMPERATURE="$2"; shift 2 ;;
        --max-tokens)      MAX_TOKENS="$2"; shift 2 ;;
        --task)            TASK="$2"; shift 2 ;;
        --estimated-saved) ESTIMATED_SAVED="$2"; shift 2 ;;
        --no-log)          NO_LOG=1; shift ;;
        --raw)             RAW=1; shift ;;
        --api)             API="$2"; shift 2 ;;
        -h|--help)         sed -n '3,32p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 5 ;;
    esac
done

command -v curl >/dev/null || { echo "curl required" >&2; exit 5; }
command -v jq   >/dev/null || { echo "jq required"   >&2; exit 5; }

# Defined early so both the success and failure paths can call it.
log_outcome() {
    local outcome="$1" latency="$2" notes="${3:-}"
    local body
    body=$(jq -nc \
        --arg d "$DELEGATE" --arg c "$CAPABILITY" \
        --arg t "${TASK:-${PROMPT:0:200}}" --arg o "$outcome" \
        --arg n "$notes" \
        --argjson lat "$latency" \
        --argjson sv "${ESTIMATED_SAVED:-null}" \
        '{delegate:$d, capability:$c, task_summary:$t, outcome:$o,
          latency_ms:$lat, token_savings:$sv, notes:$n}')
    curl -fsS -X POST -H "Content-Type: application/json" \
        --data "$body" "$API/delegations" >/dev/null
}

# Read prompt from file or stdin if not given inline
if [[ -z "$PROMPT" ]]; then
    if [[ -n "$PROMPT_FILE" ]]; then
        [[ -r "$PROMPT_FILE" ]] || { echo "unreadable prompt file: $PROMPT_FILE" >&2; exit 5; }
        PROMPT=$(cat "$PROMPT_FILE")
    elif [[ ! -t 0 ]]; then
        PROMPT=$(cat)
    else
        echo "no prompt — pass --prompt, --prompt-file, or pipe via stdin" >&2
        exit 5
    fi
fi

# Resolve delegate URL via the API.  Failing fast here gives a clean exit 4
# instead of curl bombing later with confusing connection errors.
URL=$(curl -fsS "$API/delegates/$DELEGATE" 2>/dev/null | jq -r '.contact.url // empty')
if [[ -z "$URL" ]]; then
    echo "could not resolve delegate $DELEGATE via $API (API down? wrong name?)" >&2
    exit 4
fi

# Build Ollama /api/chat body.  Native /api/chat is more reliable than the
# /v1/chat/completions emulation in older Ollama builds; either should work
# for this Ollama version but native is canonical.
build_body() {
    local sys_field=""
    if [[ -n "$SYSTEM" ]]; then
        sys_field=$(jq -nc --arg c "$SYSTEM" '{role:"system", content:$c}')
    fi
    local user_msg
    user_msg=$(jq -nc --arg c "$PROMPT" '{role:"user", content:$c}')

    local messages
    if [[ -n "$sys_field" ]]; then
        messages=$(jq -nc --argjson s "$sys_field" --argjson u "$user_msg" '[$s, $u]')
    else
        messages=$(jq -nc --argjson u "$user_msg" '[$u]')
    fi

    jq -nc \
        --arg model "$MODEL" \
        --argjson messages "$messages" \
        --argjson temperature "$TEMPERATURE" \
        --argjson num_predict "$MAX_TOKENS" \
        '{
            model: $model,
            messages: $messages,
            stream: false,
            options: { temperature: $temperature, num_predict: $num_predict }
        }'
}

BODY=$(build_body)

# Time the call so we have a real latency to log.
START_MS=$(date +%s%3N)
RESPONSE=$(curl -fsS -X POST -H "Content-Type: application/json" \
    --data "$BODY" "$URL/api/chat" 2>&1) || {
    LATENCY_MS=$(( $(date +%s%3N) - START_MS ))
    echo "delegate call failed (latency=${LATENCY_MS}ms): $RESPONSE" >&2
    # Still attempt to log the failure so the stats reflect reality.
    if [[ "$NO_LOG" -eq 0 ]]; then
        log_outcome "failure" "$LATENCY_MS" "delegate call failed: ${RESPONSE:0:200}" || true
    fi
    exit 4
}
LATENCY_MS=$(( $(date +%s%3N) - START_MS ))

# Extract the assistant content.  Native /api/chat returns
# {"message": {"role":"assistant", "content": "..."}, ...}
TEXT=$(echo "$RESPONSE" | jq -r '.message.content // empty')

if [[ -z "$TEXT" ]]; then
    echo "delegate returned empty content (latency=${LATENCY_MS}ms)" >&2
    echo "raw: $(echo "$RESPONSE" | head -c 400)" >&2
    if [[ "$NO_LOG" -eq 0 ]]; then
        log_outcome "refused" "$LATENCY_MS" "empty content" || true
    fi
    exit 3
fi

# Print to stdout — caller pipes / captures this.
if [[ "$RAW" -eq 1 ]]; then
    echo "$RESPONSE"
else
    printf '%s\n' "$TEXT"
fi

echo "[ok] ${DELEGATE} ${CAPABILITY} ${MODEL} ${LATENCY_MS}ms" >&2

if [[ "$NO_LOG" -eq 0 ]]; then
    log_outcome "success" "$LATENCY_MS" "" || {
        echo "[warn] logging failed (response printed above)" >&2
        exit 6
    }
fi
