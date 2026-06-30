#!/usr/bin/env bash
# =============================================================================
# script: restart-rote-api.sh
# purpose: Restart the local Rote FastAPI server so it picks up
#          config/env changes (e.g. a repointed OLLAMA_EMBED_URL in start.sh).
#          `rote up` is idempotent and will NOT restart an already-running
#          server, so an in-place config change needs this. Stops the listener
#          on the API port, relaunches via server/start.sh, waits for /healthz.
# inputs:
#   --port <n>      API port (default 5572)
#   --server <dir>  server dir (default /path/to/rote/server)
#   --timeout <s>   seconds to wait for healthz (default 30)
# outputs: "UP after Ns" + /healthz body on success; exit 1 on timeout
# touches-secrets: no
# when-to-use:    after editing start.sh / server config / embed endpoint
# when-NOT-to-use: the server is fine and you just want to start it if down —
#                  use `rote up` (idempotent, no restart)
# added: 2026-06-17
# family: restart-rote-api
# environment: posix-bash
# =============================================================================
set -uo pipefail
PORT=5572
SRV=/path/to/rote/server
TIMEOUT_S=30
while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)    PORT="$2"; shift 2 ;;
        --server)  SRV="$2"; shift 2 ;;
        --timeout) TIMEOUT_S="$2"; shift 2 ;;
        -h|--help) sed -n '3,18p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 5 ;;
    esac
done
API="http://127.0.0.1:${PORT}"

pid=$(ss -ltnp 2>/dev/null | grep ":${PORT} " | grep -oP 'pid=\K[0-9]+' | head -1)
if [[ -n "${pid:-}" ]]; then
    echo "stopping API pid $pid"
    kill "$pid" 2>/dev/null || true
    for _ in 1 2 3 4 5; do ss -ltn 2>/dev/null | grep -q ":${PORT} " || break; sleep 1; done
else
    echo "no existing listener on :${PORT}"
fi

echo "starting $SRV/start.sh"
setsid bash "$SRV/start.sh" >/tmp/sl-restart.log 2>&1 < /dev/null &

for i in $(seq 1 "$TIMEOUT_S"); do
    sleep 1
    if curl -fsS "$API/healthz" >/dev/null 2>&1; then
        echo "UP after ${i}s"
        curl -s "$API/healthz"
        exit 0
    fi
done
echo "TIMEOUT after ${TIMEOUT_S}s; tail of /tmp/sl-restart.log:" >&2
tail -25 /tmp/sl-restart.log >&2
exit 1
