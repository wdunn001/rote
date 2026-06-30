#!/usr/bin/env bash
# =============================================================================
# script: mcp-server/start.sh
# purpose: Launch the Rote MCP stdio server.  Idempotent first-run
#          venv bootstrap; on subsequent runs just execs the server.
#
# Like server/start.sh, the venv goes to ~/.cache/rote-mcp/venv/
# when the repo is on a Windows drvfs mount — pip is unhappy on /mnt/[a-z]/.
#
# This script is meant to be invoked AS A SUBPROCESS by an MCP client
# (Claude Desktop, Cursor, Continue.dev, etc.).  It speaks JSON-RPC over
# stdin/stdout; do NOT run it manually expecting a REPL.
#
# inputs:
#   SCRIPT_LIBRARY_API (env) — base URL of the rote HTTP API
#                              default http://127.0.0.1:5572
#   VENV_DIR (env)           — override venv location (absolute path)
# outputs: MCP JSON-RPC over stdio
# touches-secrets: no (the server it launches DOES read vault values
#                  server-side, but never returns them to MCP clients)
# when-to-use:    referenced from your MCP client's config (see README.md)
# when-NOT-to-use: standalone — there's no human-friendly output
# added: 2026-06-03
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

# Same drvfs detection as server/start.sh.
if [[ -z "${VENV_DIR:-}" ]]; then
    if [[ "$HERE" == /mnt/[a-z]/* ]]; then
        VENV_DIR="$HOME/.cache/rote-mcp/venv"
    else
        VENV_DIR="$HERE/.venv"
    fi
fi

if [[ ! -d "$VENV_DIR/bin" ]]; then
    # Send install diagnostics to stderr so we don't poison the MCP stdio
    # protocol on stdout.
    echo "[mcp/start.sh] first run — creating venv at $VENV_DIR" >&2
    mkdir -p "$(dirname "$VENV_DIR")"
    python3 -m venv "$VENV_DIR" >&2
    "$VENV_DIR/bin/pip" install --quiet --upgrade pip wheel >&2
    "$VENV_DIR/bin/pip" install --quiet -r requirements.txt >&2
fi

# Maintain the .venv symlink so callers that hardcode it still resolve.
if [[ "$VENV_DIR" != "$HERE/.venv" && ! -L "$HERE/.venv" ]]; then
    rm -f .venv
    ln -s "$VENV_DIR" .venv
fi

# Hand over to the server.  stdin/stdout MUST be the parent's streams for
# MCP JSON-RPC to work.
exec "$VENV_DIR/bin/python" "$HERE/server.py"
