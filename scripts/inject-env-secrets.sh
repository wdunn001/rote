#!/usr/bin/env bash
# =============================================================================
# script: inject-env-secrets.sh
# purpose: Inject named secrets from the local vault into a target .env file
#          inside a labeled idempotency block.  Claude calls this with key
#          NAMES; it never sees the bytes.  This is the deterministic,
#          auditable replacement for "LLM, write KEY=value into .env".
# inputs:
#   --env-file <path>   required, absolute path to target .env (created if missing)
#   --key <NAME>        required, repeatable — each key is injected
#   --label <text>      optional, default "vault-inject" — block label for idempotency
#   --api <url>         optional, default http://127.0.0.1:5572 — API base URL
# outputs:
#   stdout: { env_file, wrote: [{name, bytes}], missing: [names], ok: bool }
#   exit 0 on full success (all keys written), exit 3 if any key was missing
# touches-secrets: true (vault read + .env write)
# when-to-use:    populating a deploy .env from the local vault, OR
#                 re-injecting after a host wipe / .env reset, OR
#                 building dev .env from a shared vault snapshot
# when-NOT-to-use: when the .env is canonical (e.g. ./scripts/deploy.env);
#                  edit that directly.  This script is for transient
#                  re-population, not source-of-truth maintenance.
# added: 2026-06-03
# family: inject-env-secrets
# environment: posix-bash
# =============================================================================
set -euo pipefail

API="${API:-http://127.0.0.1:5572}"
LABEL="vault-inject"
ENV_FILE=""
KEYS=()

usage() {
    sed -n '3,32p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --env-file) ENV_FILE="$2"; shift 2 ;;
        --key)      KEYS+=("$2"); shift 2 ;;
        --label)    LABEL="$2"; shift 2 ;;
        --api)      API="$2"; shift 2 ;;
        -h|--help)  usage ;;
        *) echo "unknown arg: $1" >&2; usage ;;
    esac
done

if [[ -z "$ENV_FILE" || ${#KEYS[@]} -eq 0 ]]; then
    echo "usage: $0 --env-file <path> --key <NAME> [--key <NAME>...] [--label <text>]" >&2
    exit 1
fi

# Liveness check.  If the API isn't up, fail loud rather than silently fall
# back to "LLM does the inject" — that's the exact anti-pattern this script
# exists to prevent.
if ! curl -fsS -o /dev/null "$API/healthz"; then
    echo "ERROR: rote API not reachable at $API/healthz" >&2
    echo "       start it via: /path/to/rote/server/start.sh" >&2
    exit 4
fi

# Build the JSON body.  jq is required because the API takes a JSON array of
# keys; this is the one external dep we ask for and it's universally available
# on every dev / CI box we use.
if ! command -v jq >/dev/null; then
    echo "ERROR: jq is required for JSON request building" >&2
    exit 4
fi

body=$(jq -nc \
    --arg env_file "$ENV_FILE" \
    --arg label "$LABEL" \
    --argjson keys "$(printf '%s\n' "${KEYS[@]}" | jq -R . | jq -s .)" \
    '{env_file: $env_file, block_label: $label, keys: $keys}')

response=$(curl -fsS -X POST -H "Content-Type: application/json" \
    --data "$body" "$API/vault/inject")

echo "$response"

# Exit 3 if any key was missing — caller can treat that as "vault needs
# updating" without conflating with a hard error (5xx) or wrong-input (4xx).
missing=$(echo "$response" | jq -r '.missing | length')
if [[ "$missing" -gt 0 ]]; then
    exit 3
fi
