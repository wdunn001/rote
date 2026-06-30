---
slug: fastapi-semantic-search-endpoint
name: FastAPI sqlite-vec semantic-search endpoint
language: python
applies_patterns: semantic-search-with-embeddings, rag-retrieval-augmented-generation
applies_technologies: sqlite, sqlite-vec
references: 
---

# When to use
Adding semantic search over a small-to-medium corpus indexed in sqlite-vec.
The rote uses this shape for /scripts/search, /anti-patterns/search,
/design-patterns/search, /technologies/search.

# When NOT to use
Corpus > 1M rows — use a dedicated vector DB (Qdrant, Milvus).

You need hybrid search (BM25 + vector) — sqlite-vec doesn't ship it built-in.

# Placeholders
- RESOURCE: snake_case resource name (example: anti_patterns)
- VEC_TABLE: sqlite-vec virtual table name (example: anti_patterns_vec)
- ROUTE_PATH: URL path (example: /anti-patterns/search)
- OPERATION_ID: OpenAPI op id (example: search_anti_patterns)
- SELECT_COLS: columns to return alongside distance (example: slug, title, symptom)

# Snippet
```python
class ${RESOURCE_PASCAL}SearchRequest(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=50)


@app.post("${ROUTE_PATH}", operation_id="${OPERATION_ID}")
def search_${RESOURCE}(req: ${RESOURCE_PASCAL}SearchRequest) -> dict[str, Any]:
    """Semantic similarity search over ${RESOURCE}."""
    _sync_${RESOURCE}()
    q = _embed(req.query)
    with _conn() as c:
        rows = list(c.execute(
            f"""
            SELECT ${SELECT_COLS}, ${VEC_TABLE}.distance
            FROM ${VEC_TABLE}
            JOIN ${RESOURCE} ON ${RESOURCE}.rowid = ${VEC_TABLE}.rowid
            WHERE ${VEC_TABLE}.embedding MATCH ? AND k = ?
            ORDER BY ${VEC_TABLE}.distance
            """,
            (q, req.limit),
        ))
    return {"query": req.query, "matches": [_row_to_match(r) for r in rows]}
```

# Example expansion
See search_anti_patterns / search_design_patterns in server/app.py.
