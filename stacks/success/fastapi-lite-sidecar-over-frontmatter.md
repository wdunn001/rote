---
slug: fastapi-lite-sidecar-over-frontmatter
name: FastAPI lite sidecar serving on-disk frontmatter with BM25 (no DB/model)
technologies: fastapi, uvicorn, pydantic
patterns: degraded-mode-source-of-truth-sidecar, bm25-lexical-rank
context: Rote usable from a locked-down, model-less remote Cursor sandbox
outcome: success
references: server/app_lexical.py; server/start-lexical.sh
---

# What worked
- FastAPI + uvicorn + pydantic ALONE (no sqlite, no sqlite-vec, no torch, no network) boots in a constrained env and serves the full discovery surface.
- Parsing the same `scripts/*` and `anti-patterns/*.md` frontmatter the real indexer uses means zero drift and no index-build step.
- Pure-Python BM25 over the parsed corpus returned the correct top hit (distance 0.000) for the same queries the vector server answers — good enough ranking with zero model.
- Matching the real server's exact endpoint + response shapes let the existing MCP server point at it with one env var (`SCRIPT_LIBRARY_API`) and no code change.
- Building it as a separate file on a separate port (NOT the prod :5572, no `--reload`) gave zero blast radius — the live `app.py` server and its DB were provably untouched.

# What didn't
- Writes are out of scope: anti-pattern add, vault inject, and delegate dispatch are stubbed/501 in lexical mode (acceptable for a read-mostly locked-down box; a real vault/local-LLMs aren't reachable there anyway).
- Run-history is in-memory only (no persistence without the DB).
- Keyword (not semantic) ranking — queries must use real keywords; synonyms won't match.

# When to reuse
- Any service that normally leans on a native extension / model / DB but must also run somewhere that can't provide them, where the data is reconstructable from files on disk.

# When to avoid
- The full environment is available — retrofit the main server with a backward-compatible degrade flag instead of maintaining a parallel sidecar (which is drift surface).
- Large corpora needing a real inverted index, or write-heavy workloads.
