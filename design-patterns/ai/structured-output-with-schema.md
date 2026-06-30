---
slug: structured-output-with-schema
name: Structured Output with Schema
category: ai
intent: Constrain the LLM to produce JSON matching a schema so the output is parseable + validated
references: OpenAI Structured Outputs; Outlines library; sglang RadixAttention
---

# When to use
Downstream code expects a specific JSON shape (parsing extraction results, command verbs, ontology fills).

Free-text answers are fragile and break parsers under prompt drift.

Multiple LLM calls feed each other and a shared schema keeps the contract stable.

# When NOT to use
The answer is genuinely free-form prose (a summary, an explanation).

The schema is so restrictive it kills useful answers — relax it.

The model doesn't support the constraint mechanism well (older models, no JSON-mode, no schema-grammar) — use prompt-engineering + post-validation.

# Structure
Pass schema to the model (response_format json_schema, function-call return type, grammar-constrained decoding).  Validate output before using it.  Retry with feedback on schema failure.

# Example
```python
# sglang server supports JSON-schema-guided decoding:
response = client.chat.completions.create(
  model="Qwen/Qwen2.5-7B-Instruct",
  messages=[...],
  response_format={
    "type": "json_schema",
    "json_schema": {"name": "incident", "schema": INCIDENT_SCHEMA, "strict": True}
  }
)
```

# Relationships
Foundation of reliable LLM-in-pipeline.  Pairs with tool-use-function-calling.  Used by the rote dispatch-to-sglang.sh script's --schema flag.
