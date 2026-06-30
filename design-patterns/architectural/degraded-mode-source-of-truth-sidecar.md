---
slug: degraded-mode-source-of-truth-sidecar
name: Degraded-mode sidecar that reads the source-of-truth
category: architectural
intent: Serve a service's core read surface in a constrained environment by parsing the source-of-truth files directly, shedding the heavy deps (DB, native extensions, ML model, network) the normal server relies on
references: rote server/app_lexical.py; stack fastapi-lite-sidecar-over-frontmatter
---

# When to use
The normal server depends on something a target environment cannot provide: a native loadable extension (sqlite-vec) that hardened builds disable, an embedding model / GPU, or network egress to a backend.

The data the read surface needs already exists as files on disk (frontmatter, markdown, JSON) — the DB/index is a *derived* cache of those files.

You must NOT risk the running production instance. A separate sidecar (new files, different port, no shared mutable state) has zero blast radius.

Example: `app_lexical.py` parses the same `scripts/*` frontmatter the indexer consumes and ranks with pure-Python BM25, so a locked-down Cursor box gets find/list/show/run with no sqlite-vec, no torch, no model, no network — and `app.py` is never touched.

# When NOT to use
The environment can run the full server — then a sidecar is just drift surface; retrofit the main server with a backward-compatible degrade path instead (latch a capability flag, fall back per-request).

The read surface needs data that only lives in the derived index (computed aggregates with no file source) — then you can't reconstruct from source-of-truth.

Writes/persistence are required in the constrained env — a read-mostly sidecar can't provide them without re-implementing the write path.

# Key properties
- Reads source-of-truth, so it cannot drift from the canonical data.
- Matches the real server's endpoint/response shapes exactly, so existing clients (here, the MCP server) point at it via one env var with no code change.
- Dependency floor is the minimum to serve HTTP (here: fastapi+uvicorn+pydantic) — explicitly avoids importing the heavy optional deps so a box missing them still boots.
