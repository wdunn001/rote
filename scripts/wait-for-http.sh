#!/usr/bin/env bash
# =============================================================================
# script: wait-for-http.sh
# purpose: Poll an HTTP endpoint until it returns the expected status code
#          (and optionally contains an expected substring), then exit.
#          Replaces the `until curl ... ; do sleep N; done` patterns that
#          repeat across deploys, server-restart loops, and Docker-Compose
#          startup waits.
# inputs:
#   --url <url>             required
#   --status <code>         expected HTTP status (default 200)
#   --contains <substring>  optional; require response body to contain it
#   --timeout <seconds>     overall wait deadline (default 120)
#   --interval <seconds>    seconds between probes (default 2)
#   --header <h>            extra request header; repeat for multiple
#   --quiet                 only print on success / failure, not each poll
# outputs:
#   stdout: 1 line on success — "OK <url> <status> <elapsed_s>s"
#   stderr: per-poll progress unless --quiet
#   exit 0 success, 3 timed out, 4 unexpected non-retryable error, 5 bad args
# touches-secrets: no (headers can carry secrets — be careful what you pass)
# when-to-use:    waiting for a server to bind after start; waiting for a
#                 healthcheck to flip; gating a deploy on /healthz
# when-NOT-to-use: subsecond polling — use a real readiness probe
# added: 2026-06-03
# family: wait-for-http
# environment: posix-bash
# =============================================================================
set -uo pipefail

URL=""
EXPECT_STATUS=200
EXPECT_CONTAINS=""
TIMEOUT=120
INTERVAL=2
QUIET=0
declare -a HEADERS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --url)      URL="$2"; shift 2 ;;
        --status)   EXPECT_STATUS="$2"; shift 2 ;;
        --contains) EXPECT_CONTAINS="$2"; shift 2 ;;
        --timeout)  TIMEOUT="$2"; shift 2 ;;
        --interval) INTERVAL="$2"; shift 2 ;;
        --header)   HEADERS+=("-H" "$2"); shift 2 ;;
        --quiet)    QUIET=1; shift ;;
        -h|--help)  sed -n '3,22p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 5 ;;
    esac
done

[[ -n "$URL" ]] || { echo "usage: $0 --url <url> [--status N] [--contains TEXT] [--timeout S]" >&2; exit 5; }
command -v curl >/dev/null || { echo "curl required" >&2; exit 5; }

START=$(date +%s)
DEADLINE=$(( START + TIMEOUT ))
TRIES=0

while true; do
    TRIES=$((TRIES + 1))
    if [[ -n "$EXPECT_CONTAINS" ]]; then
        # Need the body to check contains — save to a tmp; cleanup on exit
        BODY=$(mktemp)
        trap "rm -f $BODY" EXIT
        STATUS=$(curl -s -o "$BODY" -w "%{http_code}" -m "$INTERVAL" "${HEADERS[@]}" "$URL" 2>/dev/null || echo "000")
        BODY_CONTENT=$(cat "$BODY")
    else
        STATUS=$(curl -s -o /dev/null -w "%{http_code}" -m "$INTERVAL" "${HEADERS[@]}" "$URL" 2>/dev/null || echo "000")
        BODY_CONTENT=""
    fi

    if [[ "$STATUS" == "$EXPECT_STATUS" ]]; then
        if [[ -z "$EXPECT_CONTAINS" || "$BODY_CONTENT" == *"$EXPECT_CONTAINS"* ]]; then
            ELAPSED=$(( $(date +%s) - START ))
            echo "OK $URL $STATUS ${ELAPSED}s ${TRIES}probes"
            exit 0
        fi
    fi

    if [[ "$QUIET" -eq 0 ]]; then
        ELAPSED=$(( $(date +%s) - START ))
        echo "  try $TRIES (${ELAPSED}s elapsed) — got status=$STATUS, want $EXPECT_STATUS" >&2
    fi

    if [[ $(date +%s) -ge "$DEADLINE" ]]; then
        echo "TIMEOUT after ${TIMEOUT}s ($TRIES probes) — last status=$STATUS" >&2
        exit 3
    fi
    sleep "$INTERVAL"
done
