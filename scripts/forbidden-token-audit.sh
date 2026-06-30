#!/usr/bin/env bash
# =============================================================================
# script: forbidden-token-audit.sh
# purpose: Grep a directory tree for forbidden tokens (component names,
#          API paths, vendor SDK imports, etc.) and report file:line
#          matches grouped by token. Replaces the ad-hoc `grep -rln
#          "Foo\|Bar\|Baz" apps/ | grep -v node_modules` patterns we
#          rerun every time a distribution / compliance / security
#          policy says "this string can no longer appear in shipped
#          UI" (e.g. "no Companion download CTA on marketing", "no
#          Azure SDK imports in apps/web", "no GCS automated link
#          anywhere").
# inputs:
#   --root <dir>             tree to scan; repeat for multiple roots
#   --token <pattern>        a forbidden token (literal substring, NOT
#                            regex unless --regex is also passed);
#                            repeat for each token
#   --regex                  treat --token values as ERE regex
#   --exclude <glob>         path glob to skip (default: node_modules,
#                            dist, build, .next, .git, __snapshots__,
#                            coverage). Repeat for additional excludes.
#   --include <glob>         file glob to limit search to (e.g.
#                            "*.tsx", "*.cs"); repeat for multiple
#   --format <text|json>     output shape (default text)
#   --strict                 exit 1 if ANY token matched anywhere
# outputs:
#   stdout: per-token, sorted file:line:context block (text) or a
#           JSON object {"<token>":[{"file":...,"line":N,"text":...}, ...]}
#   exit 0 = no matches OR matches but --strict not set; exit 1 = at
#         least one match AND --strict; exit 5 = bad args.
# touches-secrets: no
# when-to-use:    enforcing a "this string must not appear" rule across
#                 an app tree (distribution policy, deprecation sweep,
#                 vendor-SDK ban). Use in CI to fail PRs that
#                 re-introduce the forbidden surface.
# when-NOT-to-use: a one-off "where is X defined" lookup (use grep
#                 directly); a find-AND-replace (use
#                 find-replace-tree.sh).
# added: 2026-06-03
# family: forbidden-token-audit
# environment: posix-bash
# =============================================================================
set -uo pipefail

declare -a ROOTS=()
declare -a TOKENS=()
declare -a INCLUDES=()
REGEX=0
FORMAT="text"
STRICT=0
declare -a EXCLUDES=("node_modules" "dist" "build" ".next" ".git" "__snapshots__" "coverage")

while [[ $# -gt 0 ]]; do
    case "$1" in
        --root)     ROOTS+=("$2"); shift 2 ;;
        --token)    TOKENS+=("$2"); shift 2 ;;
        --regex)    REGEX=1; shift ;;
        --exclude)  EXCLUDES+=("$2"); shift 2 ;;
        --include)  INCLUDES+=("$2"); shift 2 ;;
        --format)   FORMAT="$2"; shift 2 ;;
        --strict)   STRICT=1; shift ;;
        -h|--help)  sed -n '3,33p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 5 ;;
    esac
done

if [[ ${#ROOTS[@]} -eq 0 || ${#TOKENS[@]} -eq 0 ]]; then
    echo "supply at least one --root and one --token" >&2
    exit 5
fi

# Build grep exclude/include args.
declare -a GREP_EXCLUDES=()
for d in "${EXCLUDES[@]}"; do GREP_EXCLUDES+=("--exclude-dir=$d"); done

declare -a GREP_INCLUDES=()
for g in "${INCLUDES[@]}"; do GREP_INCLUDES+=("--include=$g"); done

# Per-token grep, captured to a temp file.
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
ANY_MATCH=0

for token in "${TOKENS[@]}"; do
    out="$TMP/${token//[^a-zA-Z0-9._-]/_}.txt"
    if [[ $REGEX -eq 1 ]]; then
        grep -rnE "${GREP_EXCLUDES[@]}" "${GREP_INCLUDES[@]}" -- "$token" "${ROOTS[@]}" 2>/dev/null \
            | sort -u >"$out" || true
    else
        grep -rnF "${GREP_EXCLUDES[@]}" "${GREP_INCLUDES[@]}" -- "$token" "${ROOTS[@]}" 2>/dev/null \
            | sort -u >"$out" || true
    fi
    if [[ -s "$out" ]]; then ANY_MATCH=1; fi
done

# Render.
case "$FORMAT" in
    text)
        for token in "${TOKENS[@]}"; do
            out="$TMP/${token//[^a-zA-Z0-9._-]/_}.txt"
            count=$(wc -l <"$out" | tr -d ' ')
            printf '== %s (%s match%s) ==\n' "$token" "$count" "$([[ $count -eq 1 ]] || echo es)"
            if [[ $count -gt 0 ]]; then
                cat "$out"
            fi
            echo
        done
        ;;
    json)
        printf '{'
        first=1
        for token in "${TOKENS[@]}"; do
            [[ $first -eq 0 ]] && printf ','
            out="$TMP/${token//[^a-zA-Z0-9._-]/_}.txt"
            # Use python to JSON-escape lines safely.
            python3 - "$token" "$out" <<'PY'
import json, sys
token, path = sys.argv[1], sys.argv[2]
rows = []
try:
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if not line: continue
            # grep -n output: file:line:text
            parts = line.split(":", 2)
            if len(parts) == 3:
                rows.append({"file": parts[0], "line": int(parts[1]), "text": parts[2]})
            else:
                rows.append({"raw": line})
except FileNotFoundError:
    pass
print(json.dumps(token) + ":" + json.dumps(rows), end="")
PY
            first=0
        done
        printf '}\n'
        ;;
    *)
        echo "unknown --format: $FORMAT" >&2
        exit 5
        ;;
esac

if [[ $STRICT -eq 1 && $ANY_MATCH -ne 0 ]]; then exit 1; fi
exit 0
