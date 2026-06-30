#!/usr/bin/env bash
# =============================================================================
# script: json-tree-patch.sh
# purpose: Apply a structured patch across MANY JSON files at once: deep-set
#          fields by dot-path, idempotently prepend a provenance string to an
#          array (e.g. an audit "flags" log), and stamp scalar fields.  This is
#          the generalization of the per-refresh apply-*.mjs scripts (apply-
#          livedata / apply-hormuz / apply-climate / apply-DATE) that every data
#          refresh otherwise re-hand-rolls: set sub-factor fields, unshift a
#          dated provenance flag, bump assessed_on, write back pretty-printed.
# inputs:
#   --patch <json|@file>  required.  Map of file -> ops:
#        {
#          "<file-stem-or-path>": {
#            "set":     { "a.b.c": <val>, "x.y": <val> },   # deep-set by dot-path
#            "prepend": { "flags": "Refresh 2026-06-03 ..." }, # idempotent unshift
#            "stamp":   { "assessed_on": "2026-06-03" }      # alias of set, for clarity
#          }, ...
#        }
#   --dir <path>          base dir to resolve a key as "<key>.json" if the key
#                         is not itself an existing path (default ".")
#   --create              create intermediate dicts for "set" paths that do not
#                         exist yet (default: warn and skip the missing op, so
#                         you cannot silently fabricate structure)
#   --dry-run             print what would change; write nothing
#   --indent <n>          pretty-print indent (default 2); a trailing newline is
#                         always written (matches the repo convention)
# outputs:
#   stdout: per-file change lines + "patched <N> ops across <M> files" summary;
#           "MISSING <file> <path>" warnings to stderr.  exit 0 ok, 3 bad patch
#           JSON, 4 a target unreadable, 5 bad args
# touches-secrets: no
# when-to-use:    apply a dated data-refresh patch to a folder of records;
#                 bulk-set the same field across many JSON docs; append an audit/
#                 provenance entry to each touched file in one pass
# when-NOT-to-use: a single file + single path (use backup-and-merge-json.sh);
#                  array-index addressing or deletions (not supported)
# added: 2026-06-03
# family: json-tree-patch
# environment: posix-bash
# =============================================================================
set -uo pipefail

PATCH=""
DIR="."
CREATE=0
DRY_RUN=0
INDENT=2

while [[ $# -gt 0 ]]; do
    case "$1" in
        --patch)   PATCH="$2"; shift 2 ;;
        --dir)     DIR="$2"; shift 2 ;;
        --create)  CREATE=1; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        --indent)  INDENT="$2"; shift 2 ;;
        -h|--help) sed -n '3,42p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 5 ;;
    esac
done

[[ -n "$PATCH" ]] || { echo "usage: $0 --patch '<json or @file>' [--dir DIR] [--create] [--dry-run]" >&2; exit 5; }
command -v python3 >/dev/null || { echo "python3 required" >&2; exit 5; }

# @file notation for the patch (mirrors backup-and-merge-json.sh)
if [[ "${PATCH:0:1}" == "@" ]]; then
    PATCH_PATH="${PATCH:1}"
    [[ -r "$PATCH_PATH" ]] || { echo "unreadable patch file: $PATCH_PATH" >&2; exit 4; }
    PATCH=$(cat "$PATCH_PATH")
fi

PATCH="$PATCH" DIR="$DIR" CREATE="$CREATE" DRY_RUN="$DRY_RUN" INDENT="$INDENT" python3 << 'PY'
import json, os, sys

patch_raw = os.environ["PATCH"]
base_dir = os.environ["DIR"]
create = os.environ["CREATE"] == "1"
dry_run = os.environ["DRY_RUN"] == "1"
indent = int(os.environ["INDENT"])

try:
    patch = json.loads(patch_raw)
except json.JSONDecodeError as exc:
    sys.stderr.write(f"--patch is not valid JSON: {exc}\n")
    sys.exit(3)
if not isinstance(patch, dict):
    sys.stderr.write("--patch must be a JSON object mapping file -> ops\n")
    sys.exit(3)

def resolve(key):
    if os.path.isfile(key):
        return key
    cand = os.path.join(base_dir, key if key.endswith(".json") else key + ".json")
    return cand

_MISS = object()

def set_path(doc, dotted, value, warnings, fname):
    parts = dotted.split(".")
    cur = doc
    for k in parts[:-1]:
        if isinstance(cur, dict) and k in cur and isinstance(cur[k], dict):
            cur = cur[k]
        elif create:
            cur = cur.setdefault(k, {}) if isinstance(cur, dict) else _MISS
            if cur is _MISS:
                warnings.append(f"MISSING {fname} {dotted} (non-dict in path)")
                return False
        else:
            warnings.append(f"MISSING {fname} {dotted}")
            return False
    if not isinstance(cur, dict):
        warnings.append(f"MISSING {fname} {dotted} (parent not a dict)")
        return False
    cur[parts[-1]] = value
    return True

def prepend_path(doc, dotted, value, warnings, fname):
    parts = dotted.split(".")
    cur = doc
    for k in parts[:-1]:
        if isinstance(cur, dict):
            cur = cur.setdefault(k, {})
        else:
            warnings.append(f"MISSING {fname} {dotted} (parent not a dict)")
            return False
    leaf = parts[-1]
    arr = cur.get(leaf)
    if arr is None:
        arr = []
        cur[leaf] = arr
    if not isinstance(arr, list):
        warnings.append(f"MISSING {fname} {dotted} (target is not an array)")
        return False
    if value in arr:           # idempotent: do not duplicate the provenance entry
        return False
    arr.insert(0, value)
    return True

total_ops = 0
touched_files = 0
warnings = []

for key, ops in patch.items():
    if not isinstance(ops, dict):
        warnings.append(f"SKIP {key}: ops must be an object")
        continue
    path = resolve(key)
    try:
        doc = json.loads(open(path, encoding="utf-8").read())
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"{path}: unreadable ({exc})\n")
        sys.exit(4)

    file_ops = 0
    changes = []
    # prepend first so an audit entry lands above stamps/sets in display order
    for dotted, value in (ops.get("prepend") or {}).items():
        if prepend_path(doc, dotted, value, warnings, key):
            file_ops += 1
            changes.append(f"  prepend {dotted}")
    for section in ("set", "stamp"):
        for dotted, value in (ops.get(section) or {}).items():
            if set_path(doc, dotted, value, warnings, key):
                file_ops += 1
                changes.append(f"  {section:7s} {dotted} = {json.dumps(value)}")

    if file_ops:
        touched_files += 1
        total_ops += file_ops
        print(f"{os.path.basename(path)}  ({file_ops} op{'s' if file_ops!=1 else ''}){' [dry-run]' if dry_run else ''}")
        for c in changes:
            print(c)
        if not dry_run:
            open(path, "w", encoding="utf-8").write(json.dumps(doc, indent=indent) + "\n")

for w in warnings:
    sys.stderr.write(w + "\n")

print(f"{'[dry-run] would patch' if dry_run else 'patched'} {total_ops} ops across {touched_files} files")
PY
