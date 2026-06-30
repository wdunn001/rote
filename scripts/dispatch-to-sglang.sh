#!/usr/bin/env bash
# =============================================================================
# script: dispatch-to-sglang.sh
# purpose: Send a prompt to an sglang delegate (OpenAI-compatible /v1/chat/
#          completions), print the response to stdout, auto-log the outcome.
#          Adds `--schema` for sglang's distinctive JSON-schema-guided
#          structured output — prefer this delegate for any case that needs
#          schema-constrained JSON the way Ollama can't reliably produce.
# inputs:
#   --delegate <name>      delegate row name (default: local-sglang)
#   --capability <tag>     capability tag for logging (default: structured-output)
#   --prompt <text>        prompt text (mutually exclusive with --prompt-file / stdin)
#   --prompt-file <path>   read prompt from file
#   --system <text>        optional system prompt
#   --temperature <float>  default 0.2
#   --max-tokens <int>     default 2048
#   --schema <json>        OPTIONAL JSON Schema; if set, response is forced to
#                          conform.  Pass either the literal JSON or @path.
#   --task <text>          short summary recorded in the delegation_log
#   --estimated-saved <n>  estimated Claude output tokens NOT spent
#   --no-log               skip the delegation_log POST
#   --api <url>            override Rote API base (default 127.0.0.1:5572)
#   --raw                  emit the raw response JSON instead of just the message
# outputs:
#   stdout: assistant text (or raw JSON with --raw)
#   stderr: latency + (on failure) error message
#   exit 0 success, 3 empty content, 4 unreachable, 5 bad args, 6 logging failed
# touches-secrets: no (no auth on sglang LAN endpoint per the registry)
# when-to-use:    JSON-schema-guided generation (resume parsing, ontology
#                 extraction, command schema fill), 32K-context bulk summarization,
#                 anything that benefits from sglang's RadixAttention prefix caching
# when-NOT-to-use: cases the registry says Ollama handles better (most generic
#                  summarization at small context), embedding (Ollama only)
# added: 2026-06-03
# family: dispatch-to-sglang
# environment: posix-bash
# =============================================================================
set -euo pipefail

DELEGATE="local-sglang"
CAPABILITY="structured-output"
PROMPT=""
PROMPT_FILE=""
SYSTEM=""
TEMPERATURE="0.2"
MAX_TOKENS="2048"
SCHEMA=""
TASK=""
ESTIMATED_SAVED=""
NO_LOG=0
RAW=0
API="${API:-http://127.0.0.1:5572}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --delegate)        DELEGATE="$2"; shift 2 ;;
        --capability)      CAPABILITY="$2"; shift 2 ;;
        --prompt)          PROMPT="$2"; shift 2 ;;
        --prompt-file)     PROMPT_FILE="$2"; shift 2 ;;
        --system)          SYSTEM="$2"; shift 2 ;;
        --temperature)     TEMPERATURE="$2"; shift 2 ;;
        --max-tokens)      MAX_TOKENS="$2"; shift 2 ;;
        --schema)          SCHEMA="$2"; shift 2 ;;
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

# Prompt sources: --prompt, --prompt-file, or stdin.
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

# --schema accepts either literal JSON or @path notation (curl-style).
if [[ "${SCHEMA:0:1}" == "@" ]]; then
    SCHEMA_PATH="${SCHEMA:1}"
    [[ -r "$SCHEMA_PATH" ]] || { echo "unreadable schema file: $SCHEMA_PATH" >&2; exit 5; }
    SCHEMA=$(cat "$SCHEMA_PATH")
fi
if [[ -n "$SCHEMA" ]]; then
    echo "$SCHEMA" | jq -e . >/dev/null 2>&1 || { echo "--schema must be valid JSON" >&2; exit 5; }
fi

# Resolve delegate URL + model from the registry.  sglang exposes one model
# per server, so we read it back rather than letting the caller pick a wrong
# one.
DELEGATE_JSON=$(curl -fsS "$API/delegates/$DELEGATE" 2>/dev/null) || {
    echo "could not resolve delegate $DELEGATE via $API" >&2; exit 4
}
URL=$(echo "$DELEGATE_JSON"   | jq -r '.contact.url       // empty')
MODEL=$(echo "$DELEGATE_JSON" | jq -r '.contact.extra.model // empty')
if [[ -z "$URL" || -z "$MODEL" ]]; then
    echo "delegate $DELEGATE has incomplete contact data (url or extra.model missing)" >&2
    exit 4
fi

# Build the OpenAI-compatible /v1/chat/completions body, optionally with
# sglang's response_format JSON-schema constraint.
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

    local base
    base=$(jq -nc \
        --arg model "$MODEL" \
        --argjson messages "$messages" \
        --argjson temperature "$TEMPERATURE" \
        --argjson max_tokens "$MAX_TOKENS" \
        '{model:$model, messages:$messages, temperature:$temperature, max_tokens:$max_tokens}')

    if [[ -n "$SCHEMA" ]]; then
        # sglang accepts the OpenAI response_format json_schema shape.
        jq -nc \
            --argjson base "$base" \
            --argjson schema "$SCHEMA" \
            '$base + {response_format: {type:"json_schema", json_schema:{name:"out", strict:true, schema:$schema}}}'
    else
        echo "$base"
    fi
}

BODY=$(build_body)

START_MS=$(date +%s%3N)
RESPONSE=$(curl -fsS -X POST -H "Content-Type: application/json" \
    --data "$BODY" "$URL/v1/chat/completions" 2>&1) || {
    LATENCY_MS=$(( $(date +%s%3N) - START_MS ))
    echo "delegate call failed (latency=${LATENCY_MS}ms): $RESPONSE" >&2
    if [[ "$NO_LOG" -eq 0 ]]; then
        log_outcome "failure" "$LATENCY_MS" "delegate call failed: ${RESPONSE:0:200}" || true
    fi
    exit 4
}
LATENCY_MS=$(( $(date +%s%3N) - START_MS ))

TEXT=$(echo "$RESPONSE" | jq -r '.choices[0].message.content // empty')

if [[ -z "$TEXT" ]]; then
    echo "delegate returned empty content (latency=${LATENCY_MS}ms)" >&2
    echo "raw: $(echo "$RESPONSE" | head -c 400)" >&2
    if [[ "$NO_LOG" -eq 0 ]]; then
        log_outcome "refused" "$LATENCY_MS" "empty content" || true
    fi
    exit 3
fi

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
