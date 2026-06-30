#!/usr/bin/env bash
# =============================================================================
# script: doomed-prompt-precheck.sh
# purpose: A deterministic, local pre-flight check that rejects "doomed"
#          prompts BEFORE they cost a remote model round-trip. Catches the
#          prompts a cloud call would waste money on: empty, oversized
#          (context-overflow), secret-bearing (must never ship to a remote
#          model), and denylisted. This is the edge-side safety/format
#          pre-check from the codec-web idea, made concrete: do the cheap
#          deterministic screen on hardware you already own, and only pay the
#          remote tollbooth for prompts that can actually succeed.
# inputs:
#   --prompt <text>        prompt text (or --prompt-file, or stdin)
#   --prompt-file <path>   read prompt from a file
#   --max-chars <int>      reject if longer than this (default 24000 ~ 6k tokens)
#   --min-chars <int>      reject if shorter than this after trim (default 1)
#   --deny <substr>        reject if this literal substring appears; repeatable
#   --allow-secrets        do NOT reject on secret-looking content (default: reject)
#   --quiet                print only the verdict word (pass|doomed)
# outputs:
#   stdout: "<verdict>\t<reason>"  (verdict is pass|doomed)
#   exit 0  = pass (safe to send to a remote model)
#   exit 10 = doomed (caught locally; do NOT spend a remote round-trip)
#   exit 5  = bad args
# touches-secrets: no (it DETECTS secret-shaped content but never emits it;
#                  on a hit it reports the kind, never the bytes)
# when-to-use:    in front of any remote/cloud LLM call, especially in a batch
#                 or agent-to-agent pipeline where a fraction of prompts are
#                 structurally doomed and each wasted call is metered.
# when-NOT-to-use: as a substitute for real content moderation or auth; this
#                  is a cheap structural screen, not a policy engine.
# added: 2026-06-30
# family: doomed-prompt-precheck
# environment: posix-bash
# =============================================================================
set -euo pipefail

PROMPT=""
PROMPT_FILE=""
MAX_CHARS=24000
MIN_CHARS=1
ALLOW_SECRETS=0
QUIET=0
DENY=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prompt)        PROMPT="$2"; shift 2 ;;
        --prompt-file)   PROMPT_FILE="$2"; shift 2 ;;
        --max-chars)     MAX_CHARS="$2"; shift 2 ;;
        --min-chars)     MIN_CHARS="$2"; shift 2 ;;
        --deny)          DENY+=("$2"); shift 2 ;;
        --allow-secrets) ALLOW_SECRETS=1; shift ;;
        --quiet)         QUIET=1; shift ;;
        -h|--help)       sed -n '3,33p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 5 ;;
    esac
done

# Source the prompt.
if [[ -z "$PROMPT" ]]; then
    if [[ -n "$PROMPT_FILE" ]]; then
        [[ -r "$PROMPT_FILE" ]] || { echo "unreadable prompt file: $PROMPT_FILE" >&2; exit 5; }
        PROMPT=$(cat "$PROMPT_FILE")
    elif [[ ! -t 0 ]]; then
        PROMPT=$(cat)
    fi
fi

verdict() {
    # $1 = pass|doomed, $2 = reason ; exit code follows verdict
    if [[ "$QUIET" -eq 1 ]]; then printf '%s\n' "$1"; else printf '%s\t%s\n' "$1" "$2"; fi
    [[ "$1" == "pass" ]] && exit 0 || exit 10
}

# 1) Emptiness / underflow (trim leading+trailing whitespace).
TRIMMED="$(printf '%s' "$PROMPT" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
LEN=${#TRIMMED}
if (( LEN < MIN_CHARS )); then
    verdict doomed "empty-or-too-short (${LEN} chars < ${MIN_CHARS}); a remote call would burn a round-trip on nothing"
fi

# 2) Context overflow — oversized prompt that will blow the window.
if (( ${#PROMPT} > MAX_CHARS )); then
    verdict doomed "oversized (${#PROMPT} chars > ${MAX_CHARS}); split or summarize locally before any remote call"
fi

# 3) Secret-bearing — a raw secret must NEVER be shipped to a remote model.
#    Report only the KIND, never the matched bytes. This is the hook for the
#    client-side vault: inject the secret at the local tool boundary instead.
if [[ "$ALLOW_SECRETS" -eq 0 ]]; then
    kind=""
    if   printf '%s' "$PROMPT" | grep -qE -- '-----BEGIN [A-Z ]*PRIVATE KEY-----'; then kind="private-key-PEM"
    elif printf '%s' "$PROMPT" | grep -qE -- 'sk-[A-Za-z0-9]{20,}';                 then kind="openai-style-api-key"
    elif printf '%s' "$PROMPT" | grep -qE -- 'gh[pousr]_[A-Za-z0-9]{20,}';          then kind="github-token"
    elif printf '%s' "$PROMPT" | grep -qE -- 'AKIA[0-9A-Z]{16}';                    then kind="aws-access-key-id"
    elif printf '%s' "$PROMPT" | grep -qiE -- '(password|bearer|secret)[[:space:]]*[:=][[:space:]]*[^[:space:]]{8,}'; then kind="inline-credential"
    fi
    if [[ -n "$kind" ]]; then
        verdict doomed "secret-bearing (${kind}); refuse to send to a remote model — inject it from the vault at the local tool boundary instead"
    fi
fi

# 4) Denylist — caller-supplied forbidden substrings (literal).
for d in "${DENY[@]:-}"; do
    [[ -z "$d" ]] && continue
    if printf '%s' "$PROMPT" | grep -qF -- "$d"; then
        verdict doomed "denylisted-substring (\"$d\")"
    fi
done

verdict pass "structural screen passed (${LEN} chars)"
