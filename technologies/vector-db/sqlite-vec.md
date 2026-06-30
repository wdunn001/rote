---
slug: sqlite-vec
name: sqlite-vec
category: vector-db
implements_patterns: semantic-search-with-embeddings, rag-retrieval-augmented-generation
tags: embedded, offline-capable, open-source, sqlite-extension
references: https://github.com/asg017/sqlite-vec
---

# When to use
You want vector search in an SQLite-based app (this rote).

Single-process embedded search; no separate service to operate.

Tens of thousands to low millions of vectors — sqlite-vec handles this well.

# When NOT to use
Billions of vectors — use a dedicated vector DB (Qdrant, Milvus, Vespa).

You need distributed query — sqlite-vec is single-process.

You need hybrid search (BM25 + vector) as a built-in — sqlite-vec doesn't ship reranking.

# Limitations
- Linear scan for small datasets; ANN index (vec0) for larger.
- Embed dimension fixed at table creation (mean-pool to change).
- Distance metric is cosine by default.

# Cost
Free open-source.  Zero infra cost beyond the SQLite file.

# Alternatives
Qdrant (self-hosted, scales horizontally).  pgvector (Postgres extension; great for shared-DB apps).  Milvus (heavy, scales further).  Chroma (Python-friendly, embedded).
