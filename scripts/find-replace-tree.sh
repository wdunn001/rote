#!/usr/bin/env bash
# =============================================================================
# script: find-replace-tree.sh
# purpose: Codebase-wide find-and-replace across a directory tree with safe
#          backups, dry-run preview, glob filtering, and per-file diff
#          summary.  Replaces the
#              find . -type f -name '*.X' -exec sed -i 's/OLD/NEW/g' {} +
#          one-liners that keep getting hand-typed (and that frequently
#          touch binary files, fail to escape regex, or skip the backup
#          step).
# inputs:
#   --root <path>         tree to search (default: current directory)
#   --pattern <glob>      file glob to match; repeat to OR; default *.* —
#                         use --include / --exclude for finer control
#   --include <regex>     ERE; file path must match (repeat to OR-combine)
#   --exclude <regex>     ERE; file path must NOT match (repeat)
#   --from <text>         search text (literal by default)
#   --from-regex <regex>  ERE regex search (use instead of --from)
#   --to <text>           replacement text (literal); supports \1 group refs
#                         when used with --from-regex
#   --from-file <path>    read --from value from file
#   --to-file <path>      read --to value from file
#   --dry-run             show what would change; do not write
#   --no-backup           skip the .bak.<timestamp> copy (default ON)
#   --max-files <n>       safety bound on touched files (default 200)
#   --no-respect-gitignore  search files git would ignore (default: respects)
# outputs:
#   stdout: per-file change summary (path<TAB>matches)
#   stderr: total counts + sanity warnings
#   exit 0 success (changes made), 2 no matches found, 3 max-files exceeded,
#         4 ambiguous args, 5 bad args
# touches-secrets: no (don't substitute secrets — the replacement text appears
#                  in the script's tool args)
# when-to-use:    rename a constant across a package; replace an import path;
#                 swap a deprecated API call site
# when-NOT-to-use: structural refactors (AST level) — use codemod tools instead;
#                  diffs in binary files — exclude them
# added: 2026-06-03
# family: find-replace-tree
# environment: posix-bash
# =============================================================================
set -uo pipefail

ROOT="."
declare -a GLOBS=()
declare -a INCLUDE_REGEX=()
declare -a EXCLUDE_REGEX=()
FROM=""
TO=""
FROM_FILE=""
TO_FILE=""
USE_REGEX=0
DRY_RUN=0
DO_BACKUP=1
MAX_FILES=200
RESPECT_GITIGNORE=1

while [[ $# -gt 0 ]]; do
    case "$1" in
        --root)        ROOT="$2"; shift 2 ;;
        --pattern)     GLOBS+=("$2"); shift 2 ;;
        --include)     INCLUDE_REGEX+=("$2"); shift 2 ;;
        --exclude)     EXCLUDE_REGEX+=("$2"); shift 2 ;;
        --from)        FROM="$2"; shift 2 ;;
        --from-regex)  FROM="$2"; USE_REGEX=1; shift 2 ;;
        --to)          TO="$2"; shift 2 ;;
        --from-file)   FROM_FILE="$2"; shift 2 ;;
        --to-file)     TO_FILE="$2"; shift 2 ;;
        --dry-run)     DRY_RUN=1; shift ;;
        --no-backup)   DO_BACKUP=0; shift ;;
        --max-files)   MAX_FILES="$2"; shift 2 ;;
        --no-respect-gitignore) RESPECT_GITIGNORE=0; shift ;;
        -h|--help)     sed -n '3,32p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 5 ;;
    esac
done

[[ -n "$FROM_FILE" ]] && { [[ -r "$FROM_FILE" ]] || { echo "unreadable --from-file" >&2; exit 5; }; FROM=$(cat "$FROM_FILE"); }
[[ -n "$TO_FILE"   ]] && { [[ -r "$TO_FILE"   ]] || { echo "unreadable --to-file"   >&2; exit 5; }; TO=$(cat "$TO_FILE"); }
[[ -n "$FROM" ]] || { echo "--from (or --from-regex or --from-file) required" >&2; exit 5; }
[[ -n "$TO" || -n "$TO_FILE" ]] || { echo "--to (or --to-file) required (empty string = pass --to '')" >&2; exit 4; }

[[ -d "$ROOT" ]] || { echo "--root not a directory: $ROOT" >&2; exit 5; }

# File enumeration.  Prefer `git ls-files` when in a git repo to respect
# .gitignore; otherwise fall back to find.
list_files() {
    if [[ "$RESPECT_GITIGNORE" -eq 1 ]] && git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        git -C "$ROOT" ls-files --cached --others --exclude-standard
    else
        ( cd "$ROOT" && find . -type f -not -path './.git/*' -print | sed 's|^\./||' )
    fi
}

# Apply glob + include + exclude filters
filter_paths() {
    local path
    while read -r path; do
        # globs
        if [[ ${#GLOBS[@]} -gt 0 ]]; then
            local hit=0
            for g in "${GLOBS[@]}"; do
                # shellcheck disable=SC2053
                if [[ "$path" == $g || "$(basename "$path")" == $g ]]; then
                    hit=1; break
                fi
            done
            [[ "$hit" -eq 0 ]] && continue
        fi
        # include regex (OR)
        if [[ ${#INCLUDE_REGEX[@]} -gt 0 ]]; then
            local hit=0
            for r in "${INCLUDE_REGEX[@]}"; do
                [[ "$path" =~ $r ]] && { hit=1; break; }
            done
            [[ "$hit" -eq 0 ]] && continue
        fi
        # exclude regex (AND none-match)
        if [[ ${#EXCLUDE_REGEX[@]} -gt 0 ]]; then
            local hit=0
            for r in "${EXCLUDE_REGEX[@]}"; do
                [[ "$path" =~ $r ]] && { hit=1; break; }
            done
            [[ "$hit" -eq 1 ]] && continue
        fi
        echo "$path"
    done
}

# Count matches in a file without modifying it.  grep -c returns "0\n0" on
# some shells when its exit code is non-zero (grep exits 1 on no matches),
# so we run it under `|| true` and post-process with head/tr to guarantee a
# single numeric line.
count_matches() {
    local file="$1" raw=""
    if [[ "$USE_REGEX" -eq 1 ]]; then
        raw=$(grep -cE "$FROM" "$file" 2>/dev/null || echo 0)
    else
        raw=$(grep -cF "$FROM" "$file" 2>/dev/null || echo 0)
    fi
    # Take the first numeric token only.
    printf '%s' "$raw" | tr -d '\n' | grep -oE '^[0-9]+' || echo 0
}

# In-place substitute
do_replace() {
    local file="$1"
    if [[ "$USE_REGEX" -eq 1 ]]; then
        sed -i -E "s|$FROM|$TO|g" "$file"
    else
        # Escape sed metacharacters in literal FROM/TO so they really are literal.
        local esc_from esc_to
        esc_from=$(printf '%s\n' "$FROM" | sed -e 's/[\/&|]/\\&/g')
        esc_to=$(printf '%s\n' "$TO"     | sed -e 's/[\/&|]/\\&/g')
        sed -i "s|$esc_from|$esc_to|g" "$file"
    fi
}

# -----------------------------------------------------------------------------

cd "$ROOT" || exit 5
STAMP=$(date +%Y%m%d-%H%M%S)
TOTAL_FILES=0
TOTAL_MATCHES=0

# First pass: find files with matches
declare -a HITS=()
while read -r f; do
    [[ -z "$f" || -d "$f" || -L "$f" ]] && continue
    # Skip binary files.
    if file --mime "$f" 2>/dev/null | grep -q 'charset=binary'; then
        continue
    fi
    n=$(count_matches "$f")
    if [[ "$n" -gt 0 ]]; then
        HITS+=("$f|$n")
        TOTAL_FILES=$((TOTAL_FILES + 1))
        TOTAL_MATCHES=$((TOTAL_MATCHES + n))
    fi
done < <(list_files | filter_paths)

if [[ "$TOTAL_FILES" -eq 0 ]]; then
    echo "no matches found" >&2
    exit 2
fi

if [[ "$TOTAL_FILES" -gt "$MAX_FILES" ]]; then
    echo "$TOTAL_FILES files would change — exceeds --max-files=$MAX_FILES" >&2
    echo "re-run with --max-files=$((TOTAL_FILES + 10)) to proceed" >&2
    exit 3
fi

# Report
for h in "${HITS[@]}"; do
    printf '%s\t%s\n' "${h%%|*}" "${h##*|}"
done
echo "[find-replace-tree] $TOTAL_FILES files, $TOTAL_MATCHES total matches" >&2

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[find-replace-tree] dry-run; no changes written" >&2
    exit 0
fi

# Apply
for h in "${HITS[@]}"; do
    f="${h%%|*}"
    if [[ "$DO_BACKUP" -eq 1 ]]; then
        cp "$f" "${f}.bak.${STAMP}"
    fi
    do_replace "$f"
done

echo "[find-replace-tree] wrote $TOTAL_FILES files${DO_BACKUP:+ (.bak.${STAMP} alongside)}" >&2
