---
slug: delegate-not-consulted
title: Burned Claude tokens on bulk work that a registered local delegate could have done
hit_count: 1
token_cost: high — every uncaught instance burns hundreds to thousands of output tokens for work the local LLM/MetaMCP server would have handled in-house at no Claude cost
---

# Symptom

Claude reads a 20 KB log file, summarizes it, and reports back. The session has a registered delegate (e.g. `local-llm`) with `log-skim` capability and a >70% success rate over multiple attempts. The delegate was never consulted. The token spend was unnecessary.

Same shape: classification of 100 short items, embedding generation, batch translation, MCP tool calls available through MetaMCP — all done in-Claude when a registered delegate could have done them out-of-band.

# Root cause

The local-delegate skill is opt-in, and "should I defer this?" is easy to skip during planning. The cost of forgetting is invisible from inside the turn — tokens flow without any signal that they were wasted.

# Remedy

Before any operation whose value-add is mechanical (summarize, skim, classify, embed, extract, transcode), run:

```bash
rote delegate best <capability>
```

If it returns a qualified delegate (success-rate ≥ 0.7 over ≥ 3 attempts), defer the work via the contact details in the response. If no qualified delegate exists OR the operation requires Claude's reasoning, proceed in-Claude.

ALWAYS log the outcome after the work, even if you didn't defer:

```bash
rote delegate log <name> <capability> <outcome> --task "<summary>" --latency-ms N --saved N
```

That's the only way the stats stay honest. Future-Claude only knows what past-Claude wrote down.

# Detection

If you've just finished an operation that read >5 KB of input and produced a short summary, and you can name the capability (`log-skim`, `bulk-summarization`, `doc-skim`), ask: "did I check the delegate registry first?" If no, that's the smell — record it as `failure` with `--task "did this in-Claude instead of consulting delegate"` so the gap is visible.

# See also

- [[local-delegate]] skill
- `/path/to/rote/server/README.md` — API reference
