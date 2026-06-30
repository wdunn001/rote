#!/usr/bin/env bash
# =============================================================================
# script: ssh-exec.sh
# purpose: Run a command on a remote SSH-reachable host with consistent
#          timeout + capture + logging.  Replaces ad-hoc `ssh user@host
#          "long string of bash"` invocations that don't capture latency,
#          don't time out, and don't audit-log.
# inputs:
#   --host <user@host>     required
#   --cmd <shell>          command to run on remote; quoted as one arg
#   --cmd-file <path>      OR read command from a local file (interpolated as-is)
#   --timeout <seconds>    SSH-side timeout via timeout(1) (default 60)
#   --connect-timeout <s>  TCP connect deadline (default 10)
#   --no-log               skip the audit POST
#   --capability <tag>     log under this delegate capability if --delegate set
#                          (default: shell-exec-bulk)
#   --delegate <name>      optional — if set, the call is treated as a delegation
#                          to a "host" delegate and logged via /delegations
# outputs:
#   stdout: the command's stdout
#   stderr: the command's stderr + a `[ssh-exec] host=... rc=... latency=...ms`
#           footer
#   exit 0 + the command's exit code (passthrough), 4 connect/timeout fail,
#         5 bad args
# touches-secrets: no (don't put secrets in --cmd; use scp + a remote tmp
#                  file pattern if you need a config that contains secrets)
# when-to-use:    one-shot remote shell with capture + timeout
# when-NOT-to-use: interactive shell — use ssh directly; long-running tasks —
#                  use tmux/nohup on the remote then ssh-exec to poll
# added: 2026-06-03
# family: ssh-exec
# environment: posix-bash
# =============================================================================
set -uo pipefail

HOST=""
CMD=""
CMD_FILE=""
TIMEOUT_S=60
CONNECT_TIMEOUT=10
NO_LOG=0
CAPABILITY="shell-exec-bulk"
DELEGATE=""
API="${API:-http://127.0.0.1:5572}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --host)            HOST="$2"; shift 2 ;;
        --cmd)             CMD="$2"; shift 2 ;;
        --cmd-file)        CMD_FILE="$2"; shift 2 ;;
        --timeout)         TIMEOUT_S="$2"; shift 2 ;;
        --connect-timeout) CONNECT_TIMEOUT="$2"; shift 2 ;;
        --no-log)          NO_LOG=1; shift ;;
        --capability)      CAPABILITY="$2"; shift 2 ;;
        --delegate)        DELEGATE="$2"; shift 2 ;;
        -h|--help)         sed -n '3,24p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 5 ;;
    esac
done

[[ -n "$HOST" ]] || { echo "--host required" >&2; exit 5; }

if [[ -z "$CMD" ]]; then
    if [[ -n "$CMD_FILE" ]]; then
        [[ -r "$CMD_FILE" ]] || { echo "unreadable cmd file: $CMD_FILE" >&2; exit 5; }
        CMD=$(cat "$CMD_FILE")
    else
        echo "--cmd or --cmd-file required" >&2; exit 5
    fi
fi

START_MS=$(date +%s%3N)
timeout "$TIMEOUT_S" ssh -o ConnectTimeout="$CONNECT_TIMEOUT" "$HOST" "$CMD"
RC=$?
LATENCY_MS=$(( $(date +%s%3N) - START_MS ))

echo "[ssh-exec] host=$HOST rc=$RC latency=${LATENCY_MS}ms" >&2

if [[ "$NO_LOG" -eq 0 ]]; then
    if [[ -n "$DELEGATE" ]]; then
        # Log via /delegations (mirrors dispatch-to-* shape)
        BODY=$(python3 -c "
import json, os
print(json.dumps({
    'delegate': os.environ['DELEGATE'],
    'capability': os.environ['CAPABILITY'],
    'task_summary': os.environ['CMD'][:200],
    'outcome': 'success' if int(os.environ['RC']) == 0 else 'failure',
    'latency_ms': int(os.environ['LATENCY_MS']),
    'notes': f'ssh {os.environ[\"HOST\"]}',
}))
" DELEGATE="$DELEGATE" CAPABILITY="$CAPABILITY" CMD="$CMD" RC="$RC" LATENCY_MS="$LATENCY_MS" HOST="$HOST")
        curl -fsS -X POST -H "Content-Type: application/json" \
            -d "$BODY" "$API/delegations" >/dev/null 2>&1 || true
    fi
fi

exit "$RC"
