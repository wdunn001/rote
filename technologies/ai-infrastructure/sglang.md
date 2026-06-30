---
slug: sglang
name: sglang
category: ai-infrastructure
implements_patterns: tool-use-function-calling, structured-output-with-schema
tags: self-hosted, offline-capable, open-source, high-throughput-llm-server
references: https://github.com/sgl-project/sglang
---

# When to use
You need fast LLM serving with prefix caching (RadixAttention) — RAG with stable system prompts gets huge wins.

JSON-schema-guided decoding that actually obeys the schema (sglang's structured output is reliable).

Multi-turn workloads where the early turns are constant.

Acme uses codec-sglang at http://edge-host:30002 for structured-output tasks.

# When NOT to use
You want the simplest 'pull a model and chat' experience — Ollama is friendlier.

Single-model serving with infrequent requests — overhead doesn't pay off.

You need vision models with broad coverage — vLLM has broader support today.

# Limitations
- More operational complexity than Ollama (compile flags, more knobs).
- Model coverage smaller than vLLM (improving fast).
- Higher GPU memory footprint per model.

# Cost
Free open-source.  Same GPU hardware as Ollama.

# Alternatives
vLLM (similar perf; different tradeoffs).  Ollama (easier).  TGI by HuggingFace (production-leaning).  TensorRT-LLM (NVIDIA-native, highest perf).
