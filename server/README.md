# Rote API

Local persistent HTTP backend for the Claude `chronicle`, `rote`, and `secret-handling` skills.

## Start

```bash
/path/to/rote/server/start.sh
```

First run sets up `.venv` and installs `requirements.txt` (~80 MB for the embedding model; one-time). Subsequent runs are instant.

Default bind: `127.0.0.1:5572`. **Do not expose to other interfaces** without adding auth — vault endpoints read local secrets.

Test:

```bash
curl http://127.0.0.1:5572/healthz
```

## Endpoints (v0.2)

### Discovery + search

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/healthz` | Liveness + subsystem status (sqlite-vec version, embed model loaded, paths) |
| `GET` | `/scripts` | List all scripts under `/path/to/rote/scripts/` with parsed frontmatter. Auto-reindexes any changed files. |
| `GET` | `/scripts/{name}` | One script's frontmatter + size |
| `POST` | `/scripts/search` | Semantic similarity search. Body: `{"query": "free text", "limit": 5}`. Returns top-k by cosine distance over `purpose + when_to_use` embeddings. |

### Vault

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/vault/keys` | List secret names + byte sizes. **Never values.** |
| `POST` | `/vault/has` | `{"keys": ["A", "B"]}` → `{"exists": {"A": true, "B": false}}` |
| `POST` | `/vault/inject` | `{"env_file": "/abs/path/.env", "keys": ["KEY1", "KEY2"], "block_label": "..."}` → writes a labeled block to the target `.env`. Replaces prior block of the same label atomically. Response reports byte counts, not values. |

The `block_label` mechanism means re-running the same inject call is a no-op state-wise — the block is just rewritten in-place. Multiple distinct labels can coexist in one `.env`.

### Anti-patterns

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/anti-patterns` | List all (ordered by hit count desc, then last_seen desc) |
| `POST` | `/anti-patterns` | Upsert by slug. Bumps `hit_count` if slug exists; embeds the title + symptom + remedy. |
| `POST` | `/anti-patterns/search` | Semantic search by symptom or remedy text. |

### Audit

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/audit?limit=50` | Recent audit events. Payloads contain key NAMES + counts only — never bytes. |

## Data model

Single SQLite file at `data/audit.sqlite`:

- `audit_log` — append-only event log
- `anti_patterns` — slug-keyed catalog
- `anti_patterns_vec` — sqlite-vec virtual table, rowid joined to `anti_patterns`
- `script_index` — path-keyed cache of frontmatter + mtime
- `script_vec` — sqlite-vec virtual table, rowid joined to `script_index`

Embeddings are 384-dim float32 from `all-MiniLM-L6-v2`. Stored as the byte buffer sqlite-vec wants (`struct.pack("384f", ...)`).

## Operational notes

- **Restart safety**: state is in the SQLite file + the on-disk scripts + the vault JSON. Restart the uvicorn process whenever, no shutdown ceremony needed.
- **Backups**: `cp data/audit.sqlite data/audit.sqlite.$(date +%Y%m%d)`. The vault JSON is the other valuable file; back that up separately.
- **Reset embeddings**: `DELETE FROM script_vec; DELETE FROM anti_patterns_vec;` — next list/search re-embeds everything.
- **Reset audit**: `DELETE FROM audit_log;` if it grows too big. We don't auto-prune.
- **Different embedding model**: change `EMBED_MODEL_NAME` + `EMBED_DIM` in `app.py`, then reset the vec tables.

## Logs

uvicorn logs to stdout. For long-running operation, run under systemd / tmux / a process manager:

```bash
# tmux example
tmux new -s scriptlib -d '/path/to/rote/server/start.sh'
tmux attach -t scriptlib
```

## Security model

- Listens on 127.0.0.1 only.
- No auth (same-host trust model).
- Vault endpoints never echo secret values.
- All vault touches go into `audit_log` with key names + byte counts.
- Path traversal via `..` in `env_file` is rejected.
- Inject only writes to paths ending in `.env`.

## When to bypass

The API doesn't replace direct file access for the human. If you want to:

- **Edit a script**: edit the file in `/path/to/rote/scripts/`. The API picks up the change on next list/search (mtime-based reindex).
- **Add a secret**: edit `/path/to/rote/secret-vault/secrets.json` directly. The API reads it fresh on every `/vault/*` call.
- **Add an anti-pattern by hand**: hit `POST /anti-patterns` via curl, OR write a markdown file under `/path/to/rote/anti-patterns/` (not yet auto-indexed; planned).

The API is the LLM-facing surface; the filesystem is the human-facing surface.
