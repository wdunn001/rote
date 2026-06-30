#!/usr/bin/env bash
# =============================================================================
# script: install-mcp-client-config.sh
# purpose: Detect installed MCP-aware clients (Claude Desktop, Cursor,
#          Continue.dev, Cline) and write a `rote` MCP server
#          entry into each client's config.  Idempotent — re-runs replace
#          the prior block via a labeled merge, never duplicate.
# inputs:
#   --command <path>   absolute path to the MCP server launcher
#                      (default: /path/to/rote/mcp-server/start.sh)
#   --api <url>        SCRIPT_LIBRARY_API to set in the client env
#                      (default: http://127.0.0.1:5572)
#   --clients all|<csv>  comma-separated subset (default: all)
#                       — claude-desktop, cursor, continue, cline
#   --dry-run          show what would be written without touching files
# outputs:
#   stdout: per-client INSTALLED / SKIPPED (not detected) / FAILED lines
#   exit 0 success, 5 bad args, 6 at least one detected client failed to write
# touches-secrets: no (writes only a command path + env var)
# when-to-use:    fresh machine setup; after installing a new MCP client
# when-NOT-to-use: when you've hand-customized your MCP configs and don't want
#                  them touched — use --dry-run first to confirm scope
# added: 2026-06-03
# family: install-mcp-client-config
# environment: posix-bash
# =============================================================================
set -uo pipefail

COMMAND_PATH="/path/to/rote/mcp-server/start.sh"
API="http://127.0.0.1:5572"
CLIENTS="all"
DRY_RUN=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --command) COMMAND_PATH="$2"; shift 2 ;;
        --api)     API="$2"; shift 2 ;;
        --clients) CLIENTS="$2"; shift 2 ;;
        --dry-run) DRY_RUN=1; shift ;;
        -h|--help) sed -n '3,24p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 5 ;;
    esac
done

command -v python3 >/dev/null || { echo "python3 required (for JSON edits)" >&2; exit 5; }

# Pick a Windows %APPDATA% equivalent when running on WSL.  Most users will
# have their MCP clients installed on Windows, not in the WSL distro.
detect_appdata() {
    if [[ -n "${APPDATA:-}" ]]; then
        echo "$APPDATA"
    elif [[ -d "/mnt/c/Users/${USER}/AppData/Roaming" ]]; then
        echo "/mnt/c/Users/${USER}/AppData/Roaming"
    elif compgen -G "/mnt/c/Users/*/AppData/Roaming" >/dev/null; then
        # Find a Windows user we can guess at; prefer the one with Claude
        # Desktop installed.
        for d in /mnt/c/Users/*/AppData/Roaming; do
            [[ -d "$d/Claude" ]] && { echo "$d"; return; }
        done
        echo ""
    else
        echo ""
    fi
}

APPDATA_DIR=$(detect_appdata)

# Resolved config paths.  Empty means client not detected at this location.
CLAUDE_DESKTOP_CONFIG=""
[[ -n "$APPDATA_DIR" ]] && CLAUDE_DESKTOP_CONFIG="$APPDATA_DIR/Claude/claude_desktop_config.json"
# macOS fallback
[[ -d "$HOME/Library/Application Support/Claude" ]] && \
    CLAUDE_DESKTOP_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"

CURSOR_CONFIG="$HOME/.cursor/mcp.json"
CONTINUE_CONFIG="$HOME/.continue/config.yaml"
CLINE_CONFIG="$HOME/.cline/mcp.json"   # extension-default; varies

# Helper: idempotent JSON merge.  Adds a top-level `mcpServers.rote`
# entry; replaces any existing same-key block; preserves siblings.
upsert_json_block() {
    local file="$1"
    if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "[dry-run] would upsert rote MCP server into $file"
        return 0
    fi
    mkdir -p "$(dirname "$file")"
    [[ -s "$file" ]] || echo '{}' > "$file"
    FILE="$file" COMMAND="$COMMAND_PATH" API="$API" python3 - << 'PY'
import json, os, pathlib, sys
p = pathlib.Path(os.environ["FILE"])
try:
    data = json.loads(p.read_text() or "{}")
    if not isinstance(data, dict):
        raise ValueError("config root is not a JSON object")
except Exception as exc:
    sys.stderr.write(f"  failed to parse {p}: {exc}\n")
    sys.exit(1)
servers = data.setdefault("mcpServers", {})
servers["rote"] = {
    "command": os.environ["COMMAND"],
    "env": {"SCRIPT_LIBRARY_API": os.environ["API"]},
}
p.write_text(json.dumps(data, indent=2) + "\n")
print(f"  wrote {p}")
PY
}

upsert_yaml_block() {
    # Continue.dev uses YAML; keep this dead-simple: append a labeled block
    # if missing, replace if present.
    local file="$1"
    if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "[dry-run] would upsert rote MCP server into $file"
        return 0
    fi
    mkdir -p "$(dirname "$file")"
    [[ -e "$file" ]] || touch "$file"
    FILE="$file" COMMAND="$COMMAND_PATH" API="$API" python3 - << 'PY'
# Continue.dev config is YAML.  We use a deliberately-naive labeled-block
# pattern (matches the .env injection pattern from inject-env-secrets.sh)
# so we don't need a YAML lib in the system venv.
import os, pathlib, re
p = pathlib.Path(os.environ["FILE"])
text = p.read_text() if p.exists() else ""
block = (
    "# >>> rote-mcp >>>\n"
    "mcpServers:\n"
    "  - name: rote\n"
    f"    command: {os.environ['COMMAND']}\n"
    "    env:\n"
    f"      SCRIPT_LIBRARY_API: {os.environ['API']}\n"
    "# <<< rote-mcp <<<\n"
)
pattern = re.compile(r"# >>> rote-mcp >>>.*?# <<< rote-mcp <<<\n",
                     re.DOTALL)
if pattern.search(text):
    text = pattern.sub(block, text)
else:
    if text and not text.endswith("\n"):
        text += "\n"
    text += block
p.write_text(text)
print(f"  wrote {p}")
PY
}

INSTALLED=0
FAILED=0

want() {
    [[ "$CLIENTS" == "all" ]] && return 0
    [[ ",$CLIENTS," == *",$1,"* ]] && return 0
    return 1
}

# Claude Desktop
if want claude-desktop; then
    if [[ -n "$CLAUDE_DESKTOP_CONFIG" && ( -d "$(dirname "$CLAUDE_DESKTOP_CONFIG")" || -e "$CLAUDE_DESKTOP_CONFIG" ) ]]; then
        echo "[claude-desktop] detected at $CLAUDE_DESKTOP_CONFIG"
        if upsert_json_block "$CLAUDE_DESKTOP_CONFIG"; then
            INSTALLED=$((INSTALLED+1))
        else
            FAILED=$((FAILED+1))
        fi
    else
        echo "[claude-desktop] NOT DETECTED — skip"
    fi
fi

# Cursor
if want cursor; then
    if [[ -d "$HOME/.cursor" || -d "/mnt/c/Users/${USER}/.cursor" ]]; then
        # Prefer WSL-side if it exists; fallback to Windows-side.
        if [[ -d "$HOME/.cursor" ]]; then
            CFG="$CURSOR_CONFIG"
        else
            CFG="/mnt/c/Users/${USER}/.cursor/mcp.json"
        fi
        echo "[cursor] detected at $CFG"
        if upsert_json_block "$CFG"; then
            INSTALLED=$((INSTALLED+1))
        else
            FAILED=$((FAILED+1))
        fi
    else
        echo "[cursor] NOT DETECTED — skip"
    fi
fi

# Continue.dev
if want continue; then
    if [[ -d "$HOME/.continue" || -e "$CONTINUE_CONFIG" ]]; then
        echo "[continue] detected at $CONTINUE_CONFIG"
        if upsert_yaml_block "$CONTINUE_CONFIG"; then
            INSTALLED=$((INSTALLED+1))
        else
            FAILED=$((FAILED+1))
        fi
    else
        echo "[continue] NOT DETECTED — skip"
    fi
fi

# Cline (VS Code extension) — config path varies; warn rather than guess.
if want cline; then
    if compgen -G "$HOME/.vscode-server/data/User/globalStorage/saoudrizwan.claude-dev/" >/dev/null 2>&1 \
       || compgen -G "/mnt/c/Users/${USER}/AppData/Roaming/Code/User/globalStorage/saoudrizwan.claude-dev/" >/dev/null 2>&1; then
        echo "[cline] DETECTED — but cline's MCP config lives in VS Code settings."
        echo "        Add to VS Code settings.json:"
        echo "        \"cline.mcp.servers\": {"
        echo "          \"rote\": {"
        echo "            \"command\": \"$COMMAND_PATH\","
        echo "            \"env\": {\"SCRIPT_LIBRARY_API\": \"$API\"}"
        echo "          }"
        echo "        }"
    else
        echo "[cline] NOT DETECTED — skip"
    fi
fi

echo
echo "Done. Installed: $INSTALLED   Failed: $FAILED"
[[ "$FAILED" -gt 0 ]] && exit 6
exit 0
