#!/usr/bin/env bash
# =============================================================================
# script: ssh-docker-restart.sh
# purpose: Restart a Docker container on a remote SSH-reachable host, wait for
#          health, optionally run a pre-restart fix command if the container
#          is in a known-bad state (bind-mount missing, dependency restart
#          needed, etc.). One-shot remote container ops without sshing
#          interactively.
# inputs:
#   --host <user@host>     required, e.g. user@edge-host
#   --container <name>     required, container name on the remote
#   --action <verb>        start | restart | stop  (default: restart)
#   --pre-cmd <shell>      optional command run on the remote BEFORE the
#                          docker action (e.g. recover a missing bind mount).
#                          Runs as the SSH user; quote shell metacharacters.
#   --wait-healthy <sec>   poll `docker inspect` for health=healthy after the
#                          action; 0 to skip (default: 60)
#   --no-log               skip the delegations log entry
# outputs:
#   stdout: container status line(s)
#   stderr: progress + any error from the remote
#   exit 0 healthy after action, 3 unhealthy after wait, 4 ssh/docker error,
#         5 bad args
# touches-secrets: no (no env vars passed over the wire)
# when-to-use:    revive a crashed container; rotate a config-mounted container;
#                 recover a container whose host bind path is broken
# when-NOT-to-use: containers requiring docker compose orchestration — use
#                  ssh-docker-compose.sh (not yet built; promote one when needed)
# added: 2026-06-03
# family: ssh-docker-restart
# environment: posix-bash
# =============================================================================
set -uo pipefail

HOST=""
CONTAINER=""
ACTION="restart"
PRE_CMD=""
WAIT_HEALTHY=60
NO_LOG=0
API="${API:-http://127.0.0.1:5572}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --host)         HOST="$2"; shift 2 ;;
        --container)    CONTAINER="$2"; shift 2 ;;
        --action)       ACTION="$2"; shift 2 ;;
        --pre-cmd)      PRE_CMD="$2"; shift 2 ;;
        --wait-healthy) WAIT_HEALTHY="$2"; shift 2 ;;
        --no-log)       NO_LOG=1; shift ;;
        -h|--help)      sed -n '3,26p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 5 ;;
    esac
done

[[ -n "$HOST" && -n "$CONTAINER" ]] \
    || { echo "usage: $0 --host user@host --container NAME [--action restart|start|stop] [--pre-cmd 'shell']" >&2; exit 5; }
[[ "$ACTION" =~ ^(start|restart|stop)$ ]] \
    || { echo "--action must be start, restart, or stop" >&2; exit 5; }

START=$(date +%s)

if [[ -n "$PRE_CMD" ]]; then
    echo "[ssh-docker-restart] running pre-cmd on $HOST" >&2
    if ! ssh -o ConnectTimeout=10 "$HOST" "$PRE_CMD" >&2; then
        echo "[ssh-docker-restart] pre-cmd FAILED" >&2
        exit 4
    fi
fi

echo "[ssh-docker-restart] $ACTION $CONTAINER on $HOST" >&2
if ! ssh "$HOST" "docker $ACTION $CONTAINER"; then
    echo "[ssh-docker-restart] docker $ACTION FAILED" >&2
    exit 4
fi

if [[ "$ACTION" == "stop" || "$WAIT_HEALTHY" -eq 0 ]]; then
    ssh "$HOST" "docker inspect -f '{{.State.Status}} {{.State.Health.Status}}' $CONTAINER" || true
    exit 0
fi

# Poll health.  A container without a HEALTHCHECK returns "" for Status —
# treat that as a pass after a single Status=running check.
DEADLINE=$(( $(date +%s) + WAIT_HEALTHY ))
while true; do
    STATUS_LINE=$(ssh "$HOST" "docker inspect -f '{{.State.Status}}|{{.State.Health.Status}}' $CONTAINER" 2>/dev/null || true)
    STATE="${STATUS_LINE%%|*}"
    HEALTH="${STATUS_LINE#*|}"
    if [[ "$STATE" == "running" ]]; then
        if [[ "$HEALTH" == "healthy" || -z "$HEALTH" || "$HEALTH" == "<no value>" ]]; then
            DURATION=$(( $(date +%s) - START ))
            echo "$STATUS_LINE  (${DURATION}s)"
            if [[ "$NO_LOG" -eq 0 ]]; then
                curl -fsS -X POST -H "Content-Type: application/json" \
                    "$API/audit" -d "$(printf '{"kind":"ssh.docker.restart","payload":{"host":%s,"container":%s,"action":%s,"duration_s":%d}}' \
                        "\"$HOST\"" "\"$CONTAINER\"" "\"$ACTION\"" "$DURATION")" >/dev/null 2>&1 || true
            fi
            exit 0
        fi
        if [[ "$HEALTH" == "unhealthy" ]]; then
            echo "[ssh-docker-restart] container unhealthy: $STATUS_LINE" >&2
            exit 3
        fi
    fi
    if [[ $(date +%s) -gt "$DEADLINE" ]]; then
        echo "[ssh-docker-restart] timed out waiting for healthy (${WAIT_HEALTHY}s): $STATUS_LINE" >&2
        exit 3
    fi
    sleep 2
done
