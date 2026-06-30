---
slug: semantic-search-with-embeddings
name: Semantic Search with Embeddings
category: ai
intent: Find documents by meaning, not keywords, by comparing embedding vectors
references: sqlite-vec; FAISS; Chroma; pgvector
---

# When to use
Users phrase queries differently from how documents are indexed.

You want 'similar to X' as a query type, not just exact match.

You're building a RAG retrieval step.

# When NOT to use
Exact keyword match is what the user means — full-text search is faster + cheaper.

The corpus is so small embeddings are overkill.

You can't keep the index in sync with the corpus — semantic search returns plausibly-wrong results.

# Structure
Embed each document → store vector + metadata.  Embed query → cosine distance → top-k.  Optional: rerank with a cross-encoder for better precision on the top results.

# Example
```python
# The rote uses sqlite-vec for this:
def search(query: str, k: int = 5):
    qvec = embed(query)
    return db.execute(
        "SELECT slug, distance FROM scripts_vec WHERE embedding MATCH ? AND k = ?",
        (qvec, k)
    ).fetchall()
```

# Relationships
Foundation of RAG.  Pairs with hybrid-search (combine with BM25 keyword for best results).  Used throughout the rote (scripts, anti-patterns, design-patterns, technologies).
