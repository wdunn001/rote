---
slug: rote-fastapi-sqlite-vec-ollama
name: FastAPI + SQLite + sqlite-vec + Ollama-embedding (this repo)
technologies: fastapi, sqlite, sqlite-vec, ollama
patterns: rag-retrieval-augmented-generation, semantic-search-with-embeddings, repository-pattern, service-layer
context: wdunn001/rote — local context system, this repo
outcome: success
references: https://github.com/wdunn001/rote
---

# What worked
- FastAPI's auto-generated OpenAPI exposed the whole system to MCP + function-calling LLMs with zero extra work
- sqlite-vec at < 1M vectors is plenty fast for semantic search
- Switching from sentence-transformers (80MB torch dep + drvfs install fragility) to Ollama's nomic-embed-text dropped install time from ~5 min to instant
- Same SQLite file holds audit log, anti-patterns, design-patterns, technologies, snippets, stacks, scripts index, delegation log, script run log — one transactional surface for the whole system
- FastMCP wraps the HTTP API as MCP tools without re-implementing anything

# What didn't
- pip install on drvfs (Windows-mounted /mnt/h/) corrupted the venv repeatedly — moved venv to ~/.cache/ on WSL native
- sentence-transformers + torch installs take 5+ minutes on drvfs and produce zero-byte __init__.py files when interrupted

# When to reuse
- Local-first / single-host RAG systems
- Embedded vector search up to ~1M documents
- Any 'one server many client types' shape (MCP + HTTP + GUI from one backend)

# When to avoid
- Multi-node distributed deployment (sqlite-vec is single-process)
- Strict horizontal scale (use Qdrant + Postgres pair instead)
