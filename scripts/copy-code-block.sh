#!/usr/bin/env bash
# =============================================================================
# script: copy-code-block.sh
# purpose: Copy a region of a source file into a target file, anchored by
#          regex or line range.  Replaces the Read-then-Write-line-by-line
#          loop we keep running when copying a class / function / config
#          block between files.
# inputs:
#   --src <path>            source file (required)
#   --dst <path>            destination file (required; created if missing)
#   --src-from <regex>      ERE matching the FIRST line of the block (inclusive)
#   --src-to <regex>        ERE matching the LAST line of the block (inclusive)
#                           --src-from / --src-to may be omitted to copy the
#                           whole file
#   --src-lines <N:M>       OR explicit line range (1-indexed, inclusive)
#   --dst-anchor <regex>    ERE matching the line in --dst AFTER which the
#                           block is inserted; if omitted, appends to EOF
#   --dst-replace-block <regex_from> <regex_to>
#                           replace an existing block in --dst rather than
#                           inserting.  --dst-anchor is ignored.
#   --transform <command>   pass the block through `sh -c "command"` before
#                           writing (e.g. 'sed s/foo/bar/g')
#   --no-backup             skip the .bak.<timestamp> copy on --dst (default ON)
#   --dry-run               print what would be done; do not write
# outputs:
#   stdout: block being copied (or summary)
#   stderr: progress
#   exit 0 success, 2 source block empty, 3 dst-anchor not found, 4 unreadable,
#         5 bad args
# touches-secrets: no (don't transit secrets through this — use vault flows)
# when-to-use:    copy a function / class / config block; mirror a config
#                 section between configs; promote a tmp snippet into a
#                 library script
# when-NOT-to-use: large structural code moves — use AST refactor tools
# added: 2026-06-03
# family: copy-code-block
# environment: posix-bash
# =============================================================================
set -uo pipefail

SRC=""
DST=""
SRC_FROM=""
SRC_TO=""
SRC_LINES=""
DST_ANCHOR=""
DST_REPLACE_FROM=""
DST_REPLACE_TO=""
TRANSFORM=""
DO_BACKUP=1
DRY_RUN=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --src)              SRC="$2"; shift 2 ;;
        --dst)              DST="$2"; shift 2 ;;
        --src-from)         SRC_FROM="$2"; shift 2 ;;
        --src-to)           SRC_TO="$2"; shift 2 ;;
        --src-lines)        SRC_LINES="$2"; shift 2 ;;
        --dst-anchor)       DST_ANCHOR="$2"; shift 2 ;;
        --dst-replace-block)
            DST_REPLACE_FROM="$2"; DST_REPLACE_TO="$3"; shift 3 ;;
        --transform)        TRANSFORM="$2"; shift 2 ;;
        --no-backup)        DO_BACKUP=0; shift ;;
        --dry-run)          DRY_RUN=1; shift ;;
        -h|--help)          sed -n '3,32p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 5 ;;
    esac
done

[[ -n "$SRC" && -n "$DST" ]] || { echo "--src and --dst required" >&2; exit 5; }
[[ -r "$SRC" ]]              || { echo "unreadable: $SRC" >&2; exit 4; }

# Extract the block from SRC
extract_block() {
    if [[ -n "$SRC_LINES" ]]; then
        local from="${SRC_LINES%:*}" to="${SRC_LINES#*:}"
        sed -n "${from},${to}p" "$SRC"
    elif [[ -n "$SRC_FROM" || -n "$SRC_TO" ]]; then
        local from="${SRC_FROM:-^.*$}" to="${SRC_TO:-^.*$}"
        # Emit lines from the first match of FROM through the next match of TO
        awk -v from="$from" -v to="$to" '
            BEGIN { state=0 }
            state==0 && $0 ~ from { state=1 }
            state==1 { print }
            state==1 && $0 ~ to { state=2; exit }
        ' "$SRC"
    else
        cat "$SRC"
    fi
}

BLOCK=$(extract_block)

if [[ -z "$BLOCK" ]]; then
    echo "[copy-code-block] empty source block — check --src-from / --src-to / --src-lines" >&2
    exit 2
fi

if [[ -n "$TRANSFORM" ]]; then
    BLOCK=$(printf '%s' "$BLOCK" | sh -c "$TRANSFORM")
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "=== block to write to $DST ==="
    printf '%s\n' "$BLOCK"
    echo "=== end block ==="
    exit 0
fi

if [[ "$DO_BACKUP" -eq 1 && -f "$DST" ]]; then
    STAMP=$(date +%Y%m%d-%H%M%S)
    cp "$DST" "${DST}.bak.${STAMP}"
fi

mkdir -p "$(dirname "$DST")"
[[ -e "$DST" ]] || touch "$DST"

if [[ -n "$DST_REPLACE_FROM" ]]; then
    # Replace an existing block in DST
    TMP=$(mktemp)
    BLOCK="$BLOCK" awk -v from="$DST_REPLACE_FROM" -v to="$DST_REPLACE_TO" '
        BEGIN { in_block=0; printed=0 }
        in_block==0 && $0 ~ from { in_block=1; print ENVIRON["BLOCK"]; printed=1; next }
        in_block==1 && $0 ~ to   { in_block=0; next }
        in_block==1              { next }
        { print }
        END {
            if (printed==0) {
                # FROM never matched; append at EOF.
                print ENVIRON["BLOCK"]
            }
        }
    ' "$DST" > "$TMP"
    mv "$TMP" "$DST"
elif [[ -n "$DST_ANCHOR" ]]; then
    if ! grep -E -q "$DST_ANCHOR" "$DST"; then
        echo "[copy-code-block] --dst-anchor regex did not match in $DST" >&2
        exit 3
    fi
    TMP=$(mktemp)
    BLOCK="$BLOCK" awk -v anchor="$DST_ANCHOR" '
        { print }
        $0 ~ anchor { print ENVIRON["BLOCK"] }
    ' "$DST" > "$TMP"
    mv "$TMP" "$DST"
else
    # Append at EOF
    printf '%s\n' "$BLOCK" >> "$DST"
fi

LINES=$(printf '%s\n' "$BLOCK" | wc -l)
echo "[copy-code-block] wrote $LINES lines to $DST" >&2
