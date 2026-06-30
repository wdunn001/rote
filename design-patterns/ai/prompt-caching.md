---
slug: prompt-caching
name: Prompt Caching
category: ai
intent: Cache stable prompt prefixes so repeated calls pay near-zero token cost for them
references: Anthropic Prompt Caching docs; OpenAI prompt caching
---

# When to use
Long, repeated system prompts (skill stacks, large RAG context, persona descriptions).

Multi-turn conversations where the early turns don't change.

Token cost matters: caching cuts repeated tokens from ~$X/1M to ~$X/10M for cached portions.

Anthropic's prompt cache has a 5-minute TTL; calls within 5 min of each other reuse the cache.

# When NOT to use
Prompts change every call — nothing to cache.

You can't structure the prompt to put stable parts first.

The marginal cost saved isn't worth the engineering — for low-volume apps.

# Structure
Put stable content FIRST in the prompt: system instructions → tool definitions → skill bodies → retrieved RAG chunks → conversation history → current user message.  Mark cache breakpoints (Anthropic) or rely on automatic prefix matching (OpenAI).

# Example
```python
client.messages.create(
    model="claude-opus-4-8",
    system=[
        {"type": "text", "text": LARGE_SYSTEM_PROMPT},
        {"type": "text", "text": SKILL_BODIES, "cache_control": {"type": "ephemeral"}},
    ],
    messages=[...]
)
```

# Relationships
Foundational for cost-efficient LLM apps.  Pairs with skill-based-prompting (skill bodies are stable → cacheable).  Pairs with rag-retrieval-augmented-generation (retrieved chunks may or may not be cacheable depending on volatility).
