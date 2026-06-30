#!/usr/bin/env bash
# =============================================================================
# script: json-tree-get.sh
# purpose: Dump selected dot-path fields from every JSON file in a directory
#          (or an explicit file list).  The read-only companion to
#          json-tree-patch.sh: use it to see current values BEFORE authoring a
#          patch, or to spot-audit a field across a dataset.  Generalizes the
#          ad-hoc "node -e read each file and print sub_factor.score" recon we
#          write before every data refresh.
# inputs:
#   --dir <path>         directory of *.json files (default ".")
#   --files <a,b,...>    explicit comma-separated file list (overrides --dir)
#   --paths <p1,p2,...>  required; dot-paths to print (e.g.
#                        "categories.institutional.sub_factors.press_freedom.score")
#   --include-underscore include files whose name starts with "_" (default: skip)
#   --json               emit one JSON object per file instead of text lines
# outputs:
#   stdout: per file, the file name then "  <path> = <value>" lines;
#           a missing path prints "<MISSING>".  exit 0 ok, 4 unreadable, 5 bad args
# touches-secrets: no
# when-to-use:    inspect current field values across many JSON docs before a
#                 patch; audit one field across a dataset (e.g. every country's
#                 transparency_tier); ground a delta so you do not guess
# when-NOT-to-use: reading one field from one file (use jq/python inline);
#                  array-index addressing (this walks dict keys only)
# added: 2026-06-03
# family: json-tree-get
# environment: posix-bash
# =============================================================================
set -uo pipefail

DIR="."
FILES=""
PATHS=""
INCLUDE_UNDERSCORE=0
AS_JSON=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dir)                DIR="$2"; shift 2 ;;
        --files)              FILES="$2"; shift 2 ;;
        --paths)              PATHS="$2"; shift 2 ;;
        --include-underscore) INCLUDE_UNDERSCORE=1; shift ;;
        --json)               AS_JSON=1; shift ;;
        -h|--help) sed -n '3,28p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 5 ;;
    esac
done

[[ -n "$PATHS" ]] || { echo "usage: $0 --paths a.b.c[,d.e] [--dir DIR | --files a.json,b.json] [--json]" >&2; exit 5; }
command -v python3 >/dev/null || { echo "python3 required" >&2; exit 5; }

DIR="$DIR" FILES="$FILES" PATHS="$PATHS" INCLUDE_UNDERSCORE="$INCLUDE_UNDERSCORE" AS_JSON="$AS_JSON" python3 << 'PY'
import json, os, sys, glob

dir_ = os.environ["DIR"]
files_raw = os.environ["FILES"].strip()
paths = [p.strip() for p in os.environ["PATHS"].split(",") if p.strip()]
include_underscore = os.environ["INCLUDE_UNDERSCORE"] == "1"
as_json = os.environ["AS_JSON"] == "1"

if files_raw:
    files = [f.strip() for f in files_raw.split(",") if f.strip()]
else:
    files = sorted(glob.glob(os.path.join(dir_, "*.json")))
    if not include_underscore:
        files = [f for f in files if not os.path.basename(f).startswith("_")]

if not files:
    sys.stderr.write("no JSON files matched\n")
    sys.exit(4)

_MISSING = object()

def dig(obj, dotted):
    cur = obj
    for key in dotted.split("."):
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
        else:
            return _MISSING
    return cur

rc = 0
for f in files:
    try:
        doc = json.loads(open(f, encoding="utf-8").read())
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"{f}: unreadable ({exc})\n")
        rc = 4
        continue
    name = os.path.basename(f)
    if as_json:
        out = {"file": name}
        for p in paths:
            v = dig(doc, p)
            out[p] = None if v is _MISSING else v
        print(json.dumps(out))
    else:
        print(name)
        for p in paths:
            v = dig(doc, p)
            shown = "<MISSING>" if v is _MISSING else (
                json.dumps(v) if isinstance(v, (dict, list)) else v)
            print(f"  {p} = {shown}")
sys.exit(rc)
PY
