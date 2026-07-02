#!/usr/bin/env bash
# =============================================================================
# script: server/start.sh
# purpose: Launch the Rote API on 127.0.0.1.  First run creates a
#          venv and installs requirements.txt; subsequent runs are ~instant.
#          Idempotent — safe to re-run.
#
# **Venv location:** if the script tree is on a Windows-mounted filesystem
# (drvfs at /mnt/[a-z]/), the venv goes to ~/.cache/rote/venv/ on
# the WSL native FS and is symlinked into ./.venv — drvfs is far too slow
# (and too fragile) for the thousands of small files pip writes.  On native
# Linux / mac the venv goes inline at ./.venv.  Override with VENV_DIR.
#
# inputs:
#   PORT (env) — listen port, default 5572
#   HOST (env) — listen host, default 127.0.0.1 (DO NOT change to 0.0.0.0
#                without adding auth; the vault endpoints read local secrets)
#   VENV_DIR (env) — override the venv location (absolute path)
# outputs: uvicorn foreground process; logs to stdout
# touches-secrets: false (the server it launches DOES, but this launcher
#                  itself only runs `uvicorn app:app`)
# when-to-use:    starting the API for a Claude session that needs it
# when-NOT-to-use: when the service is already running on $PORT — `curl
#                  http://127.0.0.1:$PORT/healthz` checks first
# added: 2026-06-03
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

PORT="${PORT:-5572}"
HOST="${HOST:-127.0.0.1}"

# Embedding backend. By DEFAULT Rote runs fully self-contained: it falls back
# to a bundled sentence-transformers model (all-MiniLM-L6-v2, 384-dim, ~80 MB,
# downloaded once) so semantic search works with no external services.
#
# To offload embeddings to an Ollama endpoint you own (nomic-embed-text, mean-
# pooled to 384-dim so the schema is unchanged), export OLLAMA_EMBED_URL before
# invoking, e.g.:
#
#   OLLAMA_EMBED_URL=http://localhost:11434 ./server/start.sh
#
# Note: sentence-transformers' many-small-files install is slow/fragile on a
# Windows-mounted filesystem (drvfs); on WSL the venv is relocated to
# ~/.cache below to avoid that.
export OLLAMA_EMBED_URL="${OLLAMA_EMBED_URL:-}"
export OLLAMA_EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"

# Decide where the venv lives.  drvfs (Windows mount) is far too slow for
# pip's per-file IO + corrupts partial installs — relocate the venv to WSL
# native ~/.cache/ and symlink so callers still see ./.venv.
if [[ -z "${VENV_DIR:-}" ]]; then
    if [[ "$HERE" == /mnt/[a-z]/* ]]; then
        VENV_DIR="$HOME/.cache/rote/venv"
    else
        VENV_DIR="$HERE/.venv"
    fi
fi

if [[ ! -d "$VENV_DIR/bin" ]]; then
    echo "[start.sh] first run — creating venv at $VENV_DIR + installing core deps"
    mkdir -p "$(dirname "$VENV_DIR")"
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --quiet --upgrade pip wheel
    # Core deps are small and pure-Python-ish (fastapi, uvicorn, pydantic,
    # sqlite-vec) — installable from a local index for a fully offline build.
    "$VENV_DIR/bin/pip" install --quiet -r requirements.txt
    # Local embedding deps (sentence-transformers + torch, ~2 GB, plus a model
    # downloaded from HuggingFace on first use) are ONLY needed when Rote does
    # its own embeddings. Skip them for an offline / light install by pointing
    # OLLAMA_EMBED_URL at an embed endpoint you own, or ROTE_NO_EMBED_DEPS=1.
    if [[ -z "${OLLAMA_EMBED_URL:-}" && "${ROTE_NO_EMBED_DEPS:-0}" != "1" ]]; then
        echo "[start.sh] installing local embedding deps (~2 GB; set OLLAMA_EMBED_URL to skip)"
        "$VENV_DIR/bin/pip" install --quiet -r requirements-embed.txt
    else
        echo "[start.sh] skipping local embedding deps (using OLLAMA_EMBED_URL / ROTE_NO_EMBED_DEPS)"
    fi
fi

# Maintain the ./.venv symlink so callers that hardcode .venv still work.
# Refresh it every run in case VENV_DIR changed.
if [[ "$VENV_DIR" != "$HERE/.venv" ]]; then
    rm -f .venv
    ln -s "$VENV_DIR" .venv
fi

# Sanity-check that the port isn't already taken.  We'd rather bail than
# stomp on another process.
if (echo > "/dev/tcp/$HOST/$PORT") >/dev/null 2>&1; then
    echo "[start.sh] $HOST:$PORT already responding to TCP — refusing to start a second instance" >&2
    echo "[start.sh] either curl http://$HOST:$PORT/healthz to confirm it's ours, or kill the existing process" >&2
    exit 2
fi

echo "[start.sh] starting uvicorn on $HOST:$PORT"
exec .venv/bin/uvicorn app:app \
    --host "$HOST" \
    --port "$PORT" \
    --log-level info
