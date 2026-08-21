#!/usr/bin/env bash
# =============================================================================
# script: rsync-compose-deploy.sh
# purpose: Ship a local source tree to a remote host over rsync, then bring the
#          stack up with `docker compose up -d --build` over SSH, and optionally
#          gate success on an HTTP health check. Replaces the one-off
#          "rsync then ssh 'cd dir && docker compose up' then curl | grep"
#          deploy snippet that gets hand-written (slightly differently, with no
#          health gate) for every small self-hosted project.
# inputs:
#   --src <path>            required; local source dir to sync (its CONTENTS)
#   --host <user@host>      required; SSH target, e.g. deploy@example.com
#   --dest <path>           required; remote dir to sync into
#   --compose-file <path>   optional; remote path passed to `docker compose -f`
#                           (default: compose file discovered in --dest)
#   --health-url <url>      optional; if set, gate success on this URL
#   --health-contains <s>   optional; require the health response to contain s
#   --health-status <code>  optional; expected HTTP status (default 200)
#   --health-timeout <sec>  optional; overall health wait deadline (default 90)
#   --exclude <pattern>     optional; rsync --exclude; repeatable
#                           (defaults: .git node_modules dist .astro __pycache__)
#   --skip-build            rsync only; do NOT run docker compose
#   --dry-run               show what would happen; touch nothing
# outputs:
#   stdout: rsync summary, compose tail, health result
#   stderr: progress + errors
#   exit 0 success, 1 rsync failure, 2 docker compose failure,
#        3 health check failed, 5 bad args
# touches-secrets: no (do NOT sync a populated .env with this — exclude it and
#                  inject secrets on the remote at the tool boundary instead)
# when-to-use:    deploying a small compose-managed self-hosted app to a single
#                 SSH-reachable host where there is no CI/CD runner
# when-NOT-to-use: multi-host / orchestrated rollouts (use a real CD pipeline);
#                  anything needing zero-downtime or rollback semantics
# added: 2026-07-05
# family: rsync-compose-deploy
# environment: posix-bash
# =============================================================================
set -euo pipefail

SRC=""
HOST=""
DEST=""
COMPOSE_FILE=""
HEALTH_URL=""
HEALTH_CONTAINS=""
HEALTH_STATUS=200
HEALTH_TIMEOUT=90
SKIP_BUILD=0
DRY_RUN=0
declare -a EXCLUDES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --src)             SRC="$2"; shift 2 ;;
    --host)            HOST="$2"; shift 2 ;;
    --dest)            DEST="$2"; shift 2 ;;
    --compose-file)    COMPOSE_FILE="$2"; shift 2 ;;
    --health-url)      HEALTH_URL="$2"; shift 2 ;;
    --health-contains) HEALTH_CONTAINS="$2"; shift 2 ;;
    --health-status)   HEALTH_STATUS="$2"; shift 2 ;;
    --health-timeout)  HEALTH_TIMEOUT="$2"; shift 2 ;;
    --exclude)         EXCLUDES+=("$2"); shift 2 ;;
    --skip-build)      SKIP_BUILD=1; shift ;;
    --dry-run)         DRY_RUN=1; shift ;;
    -h|--help)         sed -n '3,38p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 5 ;;
  esac
done

[[ -n "$SRC"  ]] || { echo "--src required"  >&2; exit 5; }
[[ -n "$HOST" ]] || { echo "--host required (user@host)" >&2; exit 5; }
[[ -n "$DEST" ]] || { echo "--dest required" >&2; exit 5; }
[[ -d "$SRC"  ]] || { echo "source dir not found: $SRC" >&2; exit 5; }
command -v rsync >/dev/null || { echo "rsync required" >&2; exit 5; }

# Sensible default excludes if the caller passed none. Passing any --exclude
# replaces the defaults so you stay in full control when you need to.
if [[ ${#EXCLUDES[@]} -eq 0 ]]; then
  EXCLUDES=(.git node_modules dist .astro __pycache__)
fi

echo "=== rsync-compose-deploy ==="
echo "src:     $SRC"
echo "host:    $HOST"
echo "dest:    $DEST"
echo "build:   $([[ $SKIP_BUILD -eq 1 ]] && echo skip || echo yes)"
echo "health:  ${HEALTH_URL:-<none>}"
echo "dry-run: $([[ $DRY_RUN -eq 1 ]] && echo yes || echo no)"
echo

# --- rsync -----------------------------------------------------------------
RSYNC_ARGS=(-az --delete-excluded)
for e in "${EXCLUDES[@]}"; do RSYNC_ARGS+=(--exclude "$e"); done
[[ $DRY_RUN -eq 1 ]] && RSYNC_ARGS+=(--dry-run)

echo "--- rsync ---"
if ! rsync "${RSYNC_ARGS[@]}" "$SRC/" "${HOST}:${DEST}/"; then
  echo "rsync failed" >&2; exit 1
fi

# --- docker compose --------------------------------------------------------
if [[ $SKIP_BUILD -eq 0 ]]; then
  COMPOSE_FLAG=""
  [[ -n "$COMPOSE_FILE" ]] && COMPOSE_FLAG="-f $COMPOSE_FILE"
  REMOTE_CMD="cd $DEST && docker compose $COMPOSE_FLAG up -d --build"
  echo "--- docker compose up -d --build ---"
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "(dry-run) would: ssh $HOST '$REMOTE_CMD'"
  elif ! ssh "$HOST" "$REMOTE_CMD" 2>&1 | tail -20; then
    echo "docker compose failed" >&2; exit 2
  fi
fi

# --- health gate -----------------------------------------------------------
# The health poll is delegated to Rote's wait-for-http.sh (same scripts/ dir)
# rather than re-implementing the until/curl/sleep loop here — see that script
# for the polling/backoff/timeout details. This keeps one canonical health-gate
# implementation instead of a second slightly-different copy.
if [[ -n "$HEALTH_URL" && $DRY_RUN -eq 0 ]]; then
  echo "--- health ---"
  WAIT_HTTP="$(dirname "$0")/wait-for-http.sh"
  if [[ ! -x "$WAIT_HTTP" && ! -r "$WAIT_HTTP" ]]; then
    echo "health check requested but wait-for-http.sh not found next to this script" >&2
    exit 3
  fi
  HC_ARGS=(--url "$HEALTH_URL" --status "$HEALTH_STATUS" --timeout "$HEALTH_TIMEOUT")
  [[ -n "$HEALTH_CONTAINS" ]] && HC_ARGS+=(--contains "$HEALTH_CONTAINS")
  if bash "$WAIT_HTTP" "${HC_ARGS[@]}"; then
    echo "health: OK"
  else
    echo "health: FAILED — $HEALTH_URL did not become healthy in ${HEALTH_TIMEOUT}s" >&2
    exit 3
  fi
fi

echo "done."
