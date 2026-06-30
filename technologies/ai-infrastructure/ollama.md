---
slug: ollama
name: Ollama
category: ai-infrastructure
implements_patterns: tool-use-function-calling, rag-retrieval-augmented-generation, semantic-search-with-embeddings
tags: self-hosted, offline-capable, open-source, llm-server
references: https://ollama.com/; edge-host @ http://edge-host:11434
---

# When to use
You want to run open-weight LLMs locally (Llama, Qwen, Mixtral, GPT-OSS, embedding models).

OpenAI-compatible API surface so existing tooling works.

You need embedding generation (nomic-embed-text) without depending on cloud.

Acme / rote uses Ollama on edge-host for the embedding backend and as a delegate for bulk summarization.

# When NOT to use
You need frontier-model quality (Claude Opus, GPT-4, Gemini) — open weights are getting close but not equal.

You need very high throughput per server — sglang or vLLM are higher-throughput.

JSON-schema-constrained decoding — Ollama supports it but sglang is more reliable.

# Limitations
- Multi-model serving on one GPU shares memory — switching models has latency.
- Quantization changes output quality — Q4 vs Q8 matters.
- Smaller models (7B) have meaningful quality gaps from frontier; benchmark before relying.

# Cost
Free open-source server.  Hardware: a 24GB GPU runs 13B-70B comfortably.  Operational cost: ops time + electricity, vs cloud API per-token billing.

# Alternatives
vLLM (higher throughput, more complex setup).  sglang (RadixAttention + schema-guided decoding).  LM Studio (desktop UI + server).  LocalAI (compatibility-focused).
