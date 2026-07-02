# Running Rote offline

Rote is designed to run with no internet at all. The server holds no model,
makes no outbound call, and needs no external service. The only things that
ever reach the network are (1) `pip install` at first setup and (2) the
optional local embedding model download. Both have offline paths.

## 1. Core dependencies (offline)

The core is four small, pinned packages (`server/requirements.txt`): FastAPI,
uvicorn, pydantic, and sqlite-vec (which ships prebuilt binary wheels). On a
machine with internet, prefetch them once:

```bash
pip download -r server/requirements.txt -d vendor/
```

Commit or copy `vendor/` to the offline host, then install from it:

```bash
python3 -m venv server/.venv
server/.venv/bin/pip install --no-index --find-links vendor/ -r server/requirements.txt
```

Or point pip at your local index (e.g. a devpi / Nexus / Artifactory mirror)
with `PIP_INDEX_URL`. `server/start.sh` does the venv + install for you; it
installs only the core by default when embeddings are handled elsewhere (below).

## 2. Embeddings (offline) — pick one

Semantic search needs a vector for each query. Rote has two backends:

**Recommended: a local Ollama you own.** Set `OLLAMA_EMBED_URL` before starting.
`start.sh` then skips the heavy `sentence-transformers` + torch install entirely,
so setup is just the four core packages:

```bash
OLLAMA_EMBED_URL=http://localhost:11434 ./server/start.sh
```

**Or the bundled model, pre-cached.** Install the optional deps and pre-populate
the HuggingFace cache on an online box, then run offline:

```bash
pip install -r server/requirements-embed.txt          # torch + sentence-transformers
python -c "from sentence_transformers import SentenceTransformer as S; S('sentence-transformers/all-MiniLM-L6-v2')"
# copy ~/.cache/huggingface to the offline host, then:
export HF_HOME=/path/to/cache HF_HUB_OFFLINE=1
```

**Or nothing.** If neither is present, Rote still runs: the catalog lists and
serves, and search returns results, but ranking degrades to insertion order
(the embed step yields a zero vector instead of crashing). Full-text and field
filters are unaffected.

## 3. Everything else is already local

The CLI, MCP server, GUI, vault, and delegate registry all talk only to the
local FastAPI server (`127.0.0.1:5572`). The GUI ships no CDN assets. The
SQLite database is rebuilt from the on-disk catalog files, which are the source
of truth. Nothing here needs a network.
