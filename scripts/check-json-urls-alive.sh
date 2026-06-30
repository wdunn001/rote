#!/usr/bin/env bash
# =============================================================================
# script: check-json-urls-alive.sh
# purpose: Extract every http(s) URL from a JSON file and probe each one for liveness (HEAD then GET fallback, browser UA), reporting ALIVE/WARN/DEAD per URL
# family: check-json-urls-alive
# environment: posix-bash
# inputs:
#   --file <path>        JSON (or any text) file to scan for https?:// URLs (required)
#   --timeout <sec>      per-request timeout, default 15
#   --concurrency <n>    parallel probes, default 8
#   --quiet              only print the summary + DEAD/WARN lines (suppress ALIVE)
#   --strict             exit 1 when any DEAD link is found (default: always exit 0
#                        after reporting, so a link-rot report is never mistaken for
#                        a crash). Use --strict in CI to gate on link health.
# outputs:
#   stdout: one line per unique URL -> "<STATUS>\t<http_code>\t<url>"
#           then a summary line "summary: N urls | A alive | W warn | D dead"
#   STATUS: ALIVE (2xx/3xx) | WARN (401/403/405/429/5xx = reachable but blocked/transient)
#           | DEAD (000 connect-fail, 404/410/other 4xx)
#   note:   000/403 are usually anti-bot or geo blocks (site is up in a browser), NOT
#           proof the URL is wrong — treat DEAD as "needs a human eyeball", not "delete".
#   exit:   0 always (report mode); with --strict, 1 if any DEAD; 5 on bad usage
# touches-secrets: false
# when-to-use:    validating that a curated link list (regulator/law links, docs link
#                 packs, sitemap-ish JSON) still resolves; CI link-rot guard for data files
# when-NOT-to-use: polling ONE endpoint until ready (use wait-for-http.sh); parsing a
#                 /health JSON envelope per dependency (use multi-endpoint-health-probe.sh)
# added: 2026-06-04
# =============================================================================
set -uo pipefail

FILE=""
TIMEOUT=15
CONCURRENCY=8
QUIET=0
STRICT=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) sed -n '3,32p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        --file) FILE="${2:-}"; shift 2 ;;
        --timeout) TIMEOUT="${2:-}"; shift 2 ;;
        --concurrency) CONCURRENCY="${2:-}"; shift 2 ;;
        --quiet) QUIET=1; shift ;;
        --strict) STRICT=1; shift ;;
        *) echo "unknown arg: $1" >&2; exit 5 ;;
    esac
done

[[ -n "$FILE" ]] || { echo "error: --file <path> is required" >&2; exit 5; }
[[ -f "$FILE" ]] || { echo "error: file not found: $FILE" >&2; exit 5; }
command -v curl >/dev/null 2>&1 || { echo "error: curl not installed" >&2; exit 5; }

UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

# Extract unique http(s) URLs. Trim common trailing JSON/markdown punctuation.
mapfile -t URLS < <(grep -oE 'https?://[^"[:space:])<>]+' "$FILE" \
    | sed -E 's/[],.;]+$//' \
    | sort -u)

[[ ${#URLS[@]} -gt 0 ]] || { echo "error: no http(s) URLs found in $FILE" >&2; exit 5; }

# Probe one URL: print "<STATUS>\t<code>\t<url>". HEAD first; on a blocked/empty
# result fall back to a ranged GET (some servers reject HEAD or bot HEADs only).
probe_one() {
    local url="$1" timeout="$2" ua="$3" code
    code=$(curl -sS -L -I -o /dev/null -w '%{http_code}' \
        --max-time "$timeout" -A "$ua" "$url" 2>/dev/null)
    if [[ "$code" == "000" || "$code" == "403" || "$code" == "405" || "$code" == "501" ]]; then
        # retry with a real GET, asking for just the first byte
        code=$(curl -sS -L -r 0-0 -o /dev/null -w '%{http_code}' \
            --max-time "$timeout" -A "$ua" "$url" 2>/dev/null)
        # some servers ignore Range and answer 200 to GET
        [[ "$code" == "000" ]] && code=$(curl -sS -L -o /dev/null -w '%{http_code}' \
            --max-time "$timeout" -A "$ua" "$url" 2>/dev/null)
    fi
    local status
    case "$code" in
        2??|3??)            status="ALIVE" ;;
        401|403|405|429|5??) status="WARN" ;;  # reachable but blocked / transient
        000)                status="DEAD" ;;   # DNS / TCP / TLS / timeout
        *)                  status="DEAD" ;;   # 404/410/other 4xx
    esac
    printf '%s\t%s\t%s\n' "$status" "$code" "$url"
}
export -f probe_one

# Fan out, then sort the collected lines so DEAD/WARN float to the top.
RESULTS=$(printf '%s\n' "${URLS[@]}" \
    | xargs -P "$CONCURRENCY" -I{} bash -c 'probe_one "$@"' _ {} "$TIMEOUT" "$UA" \
    | sort -t$'\t' -k1,1)

alive=$(grep -c $'^ALIVE\t' <<<"$RESULTS" || true)
warn=$(grep -c  $'^WARN\t'  <<<"$RESULTS" || true)
dead=$(grep -c  $'^DEAD\t'  <<<"$RESULTS" || true)

if [[ "$QUIET" == "1" ]]; then
    grep -vE $'^ALIVE\t' <<<"$RESULTS" || true
else
    echo "$RESULTS"
fi

echo "summary: ${#URLS[@]} urls | ${alive:-0} alive | ${warn:-0} warn | ${dead:-0} dead | file=$FILE"

# Default is report-mode: a link-rot finding is a normal result, not a script failure,
# so exit 0 after printing. --strict turns DEAD links into a nonzero (CI gate) exit.
if [[ "$STRICT" == "1" && "${dead:-0}" -gt 0 ]]; then
    exit 1
fi
exit 0
