#!/usr/bin/env bash
# =============================================================================
# script: backup-and-merge-json.sh
# purpose: Idempotent edit of a JSON config file: backup first, then merge a
#          patch object into a specific path inside the JSON tree.  Replaces
#          the hand-rolled python+jq one-offs we write every time a tool
#          wants us to add a block to claude_desktop_config.json,
#          cursor/mcp.json, settings.json, package.json, etc.
# inputs:
#   --file <path>          required, target JSON file (created if missing)
#   --path <dot.path>      required, where the patch lands (e.g. "mcpServers.rote")
#   --patch <json>         required, JSON object or value to set; @path reads from file
#   --no-backup            skip the .bak.<timestamp> copy (default ON)
#   --indent <n>           pretty-print indent (default 2)
# outputs:
#   stdout: one-line summary — "wrote <file>  path=<path>  size=<bytes>"
#   exit 0 success, 3 patch invalid JSON, 4 target unreadable, 5 bad args
# touches-secrets: no (but if the value IS a secret, use vault_inject instead)
# when-to-use:    add an MCP server entry to a client config; flip a single
#                 setting in a settings.json; bump a version pin in package.json
# when-NOT-to-use: large structural rewrites (Edit the file directly); YAML
#                  configs (use backup-and-merge-yaml.sh — not yet built)
# added: 2026-06-03
# family: backup-and-merge-json
# environment: posix-bash
# =============================================================================
set -uo pipefail

FILE=""
DOTPATH=""
PATCH=""
DO_BACKUP=1
INDENT=2

while [[ $# -gt 0 ]]; do
    case "$1" in
        --file)      FILE="$2"; shift 2 ;;
        --path)      DOTPATH="$2"; shift 2 ;;
        --patch)     PATCH="$2"; shift 2 ;;
        --no-backup) DO_BACKUP=0; shift ;;
        --indent)    INDENT="$2"; shift 2 ;;
        -h|--help)   sed -n '3,22p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 5 ;;
    esac
done

[[ -n "$FILE" && -n "$DOTPATH" && -n "$PATCH" ]] \
    || { echo "usage: $0 --file PATH --path dot.path --patch '<json or @path>'" >&2; exit 5; }
command -v python3 >/dev/null || { echo "python3 required" >&2; exit 5; }

# Allow @path notation for the patch
if [[ "${PATCH:0:1}" == "@" ]]; then
    PATCH_PATH="${PATCH:1}"
    [[ -r "$PATCH_PATH" ]] || { echo "unreadable patch file: $PATCH_PATH" >&2; exit 4; }
    PATCH=$(cat "$PATCH_PATH")
fi

if [[ "$DO_BACKUP" -eq 1 && -f "$FILE" ]]; then
    STAMP=$(date +%Y%m%d-%H%M%S)
    cp "$FILE" "${FILE}.bak.${STAMP}"
fi

FILE="$FILE" DOTPATH="$DOTPATH" PATCH="$PATCH" INDENT="$INDENT" python3 << 'PY'
import json, os, pathlib, sys

p = pathlib.Path(os.environ["FILE"])
dotpath = os.environ["DOTPATH"]
patch_raw = os.environ["PATCH"]
indent = int(os.environ["INDENT"])

# Parse patch
try:
    patch = json.loads(patch_raw)
except json.JSONDecodeError as exc:
    sys.stderr.write(f"--patch is not valid JSON: {exc}\n")
    sys.exit(3)

# Load existing
if p.exists() and p.stat().st_size > 0:
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"existing file is not valid JSON: {exc}\n")
        sys.exit(4)
else:
    data = {}

# Walk the dotpath, creating intermediate dicts
parts = dotpath.split(".")
parent = data
for key in parts[:-1]:
    if not isinstance(parent, dict):
        sys.stderr.write(f"dotpath collides with non-dict at {key}\n")
        sys.exit(4)
    parent = parent.setdefault(key, {})
if not isinstance(parent, dict):
    sys.stderr.write(f"dotpath parent is not a dict: {dotpath}\n")
    sys.exit(4)
parent[parts[-1]] = patch

p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(data, indent=indent) + "\n")

print(f"wrote {p}  path={dotpath}  size={p.stat().st_size}")
PY
