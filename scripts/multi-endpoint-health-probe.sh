#!/usr/bin/env bash
# =============================================================================
# script: multi-endpoint-health-probe.sh
# purpose: Probe N HTTP surfaces in parallel and, when one of them returns a
#          structured /health/ready JSON envelope, break it down per
#          dependency check (Healthy / Degraded / Unhealthy). Replaces the
#          inline `curl -w "...: %{http_code}\n"` chains + ad-hoc
#          `python3 -c "import json; ..."` parsers that recur on every
#          deploy-verify and prod-incident triage.
# inputs:
#   --surface <label>=<url>   one HTTP surface to probe; repeat for each
#                             (e.g. --surface api=https://api.example/healthz)
#   --ready <url>             optional: full URL of a structured /health/ready
#                             endpoint to expand into per-check breakdown
#   --expect <code>           expected status per surface (default 200)
#   --timeout <s>             per-request timeout (default 10)
#   --json                    emit JSON instead of human-readable text
# outputs:
#   stdout: human-readable status (or JSON with --json):
#     api: 200
#     app: 200
#     marketing: 200
#     ---health/ready---
#     overall: Unhealthy
#       postgres: Healthy
#       ots: Unhealthy
#   exit 0 when every surface met --expect and ready (if supplied) is not
#         Unhealthy; exit 1 when any surface mismatched OR ready=Unhealthy;
#         exit 2 when ready=Degraded only (advisory); exit 5 bad args.
# touches-secrets: no (caller must not pass bearer tokens via URL)
# when-to-use:    post-deploy smoke; loop-mode prod-health ticks; triaging
#                 an "is it the API or the worker?" incident.
# when-NOT-to-use: a single endpoint poll-until-ready (use wait-for-http.sh).
# added: 2026-06-03
# family: multi-endpoint-health-probe
# environment: posix-bash
# =============================================================================
set -uo pipefail

declare -a SURFACES=()
READY_URL=""
EXPECT=200
TIMEOUT=10
JSON_OUT=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --surface)  SURFACES+=("$2"); shift 2 ;;
        --ready)    READY_URL="$2"; shift 2 ;;
        --expect)   EXPECT="$2"; shift 2 ;;
        --timeout)  TIMEOUT="$2"; shift 2 ;;
        --json)     JSON_OUT=1; shift ;;
        -h|--help)  sed -n '3,26p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 5 ;;
    esac
done

if [[ ${#SURFACES[@]} -eq 0 && -z "$READY_URL" ]]; then
    echo "supply at least one --surface or a --ready URL" >&2
    exit 5
fi

# Probe each surface; capture exit + status into TMP.
TMPDIR_PROBE="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_PROBE"' EXIT
ANY_FAIL=0

probe_one() {
    local label="$1" url="$2"
    local code
    code="$(curl -sS -o /dev/null --max-time "$TIMEOUT" -w "%{http_code}" "$url" 2>/dev/null || echo 000)"
    printf '%s\t%s\n' "$label" "$code" >"$TMPDIR_PROBE/$label.out"
}

# Fan out concurrently so a single slow surface doesn't gate the rest.
for pair in "${SURFACES[@]}"; do
    label="${pair%%=*}"
    url="${pair#*=}"
    probe_one "$label" "$url" &
done
wait

# Collect ordered results matching input order.
declare -A STATUS
for pair in "${SURFACES[@]}"; do
    label="${pair%%=*}"
    if [[ -f "$TMPDIR_PROBE/$label.out" ]]; then
        STATUS[$label]="$(cut -f2 "$TMPDIR_PROBE/$label.out")"
    else
        STATUS[$label]="000"
    fi
    if [[ "${STATUS[$label]}" != "$EXPECT" ]]; then ANY_FAIL=1; fi
done

# Optional structured /health/ready expansion.
READY_OVERALL=""
declare -a READY_CHECKS=()
if [[ -n "$READY_URL" ]]; then
    READY_BODY="$(curl -sS --max-time "$TIMEOUT" "$READY_URL" 2>/dev/null || true)"
    if [[ -n "$READY_BODY" ]]; then
        if command -v python3 >/dev/null 2>&1; then
            while IFS= read -r line; do
                [[ -z "$line" ]] && continue
                if [[ "$line" == "OVERALL:"* ]]; then
                    READY_OVERALL="${line#OVERALL:}"
                else
                    READY_CHECKS+=("$line")
                fi
            done < <(python3 - "$READY_BODY" <<'PY'
import json, sys
try:
    d = json.loads(sys.argv[1])
    print(f"OVERALL:{d.get('status', 'Unknown')}")
    for c in d.get("checks", []):
        print(f"  {c.get('name', '?')}: {c.get('status', '?')}")
except Exception as e:
    print(f"OVERALL:ParseError:{e}", file=sys.stderr)
PY
            )
        fi
    fi
fi

# Render.
if [[ $JSON_OUT -eq 1 ]]; then
    {
        printf '{"surfaces":{'
        first=1
        for pair in "${SURFACES[@]}"; do
            label="${pair%%=*}"
            [[ $first -eq 0 ]] && printf ','
            printf '"%s":%s' "$label" "${STATUS[$label]}"
            first=0
        done
        printf '},"ready":'
        if [[ -n "$READY_OVERALL" ]]; then
            printf '{"overall":"%s","checks":[' "$READY_OVERALL"
            first=1
            for c in "${READY_CHECKS[@]}"; do
                [[ $first -eq 0 ]] && printf ','
                # c is "  name: Status" -- trim + split.
                trimmed="${c##  }"
                name="${trimmed%%:*}"
                stat="${trimmed#*: }"
                printf '{"name":"%s","status":"%s"}' "$name" "$stat"
                first=0
            done
            printf ']}'
        else
            printf 'null'
        fi
        printf '}\n'
    }
else
    for pair in "${SURFACES[@]}"; do
        label="${pair%%=*}"
        printf '%s: %s\n' "$label" "${STATUS[$label]}"
    done
    if [[ -n "$READY_OVERALL" ]]; then
        echo "---health/ready---"
        printf 'overall: %s\n' "$READY_OVERALL"
        printf '%s\n' "${READY_CHECKS[@]}"
    fi
fi

# Exit code: 1 on any surface mismatch OR ready Unhealthy; 2 on ready Degraded only.
if [[ "$READY_OVERALL" == "Unhealthy"* ]]; then exit 1; fi
if [[ $ANY_FAIL -ne 0 ]]; then exit 1; fi
if [[ "$READY_OVERALL" == "Degraded"* ]]; then exit 2; fi
exit 0
