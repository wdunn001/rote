---
slug: rag-retrieval-augmented-generation
name: RAG (Retrieval-Augmented Generation)
category: ai
intent: Ground LLM responses in retrieved documents so answers reflect a specific corpus, not just training data
references: Lewis et al. 'Retrieval-Augmented Generation'; Anthropic Contextual Retrieval
---

# When to use
You need the LLM to answer from YOUR data (codebase, knowledge base, ticket history) — not its training data.

The corpus updates frequently and you can't fine-tune fast enough.

Auditability matters: citations to source documents are required.

The rote catalogs (scripts, anti-patterns, design-patterns, technologies) themselves ARE RAG — semantic search via embeddings, the LLM gets the matched documents in context.

# When NOT to use
The model already knows enough — RAG adds latency without value.

The retrieval index is stale relative to truth — confidently-cited wrong answers.

The corpus is small enough to put in the system prompt — no index needed.

# Structure
Index: embed documents, store in vector DB.  Retrieve: embed query, find top-k similar.  Augment: stuff retrieved chunks into the LLM prompt.  Generate: LLM answers conditioned on the chunks.

# Example
```python
# Rote is RAG over your own scripts + anti-patterns:
def find(query: str):
    vec = embed(query)
    chunks = sqlite_vec.search("scripts_vec", vec, k=5)
    return chunks  # LLM uses these in its next response
```

# Relationships
Foundation of LLM apps over private data.  Pairs with semantic-search-with-embeddings.  Pairs with structured-output-with-schema (force the answer to cite sources).  Variants: self-rag (model decides what to retrieve), GraphRAG (retrieval over a knowledge graph).

# Concrete implementation in this library
`scripts/dispatch-with-rag.py` is the local-LLM dispatcher that applies this pattern.  It hits every searchable catalog (scripts, design-patterns, technologies, snippets, commands, anti-patterns, stacks) in parallel, formats the top hits as an authoritative system-message preamble, and calls the local Ollama delegate.  Built to fence in [[stacks/success/local-rtx2080ti-ollama-phi3]] confabulation — first run reduced wall-clock from 68s to 13s AND the response correctly cited slugs instead of inventing them.  Use this dispatcher whenever the task is "about" the rote itself; use the plain `dispatch-to-ollama.sh` when the task isn't.
