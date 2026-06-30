---
name: design-patterns
description: Use this when (and BEFORE) you design a class hierarchy, service layer, resilience layer, offline pipeline, AI-augmented feature, or write boilerplate code. Returns proven patterns + matching technologies + parameterized code snippets + recorded stack outcomes from a curated catalog so you don't reinvent from mediocre training-data code. Catalog has cautionary entries (don't use Azure Service Bus because we need offline) so wrong choices are visible. Record new patterns/tech/stacks back.
---

# Design Patterns + Technologies — "Library Before Training Data"

Training-data code is often mediocre. The model has seen Singleton implementations done a hundred wrong ways, "circuit breakers" that don't break, "RAG pipelines" that hand-roll embedding loops, "offline-first" apps that aren't. The two local catalogs in this library are the antidote: a curated `design-patterns` catalog of GOOD patterns + a `technologies` catalog of concrete tools mapped to those patterns with explicit "when to use, when NOT, why."

**The rule:** consult the catalog before writing pattern-shaped code. Use the canonical shape. Cite which pattern + which tech you applied so the use-counts grow and we know what's load-bearing.

## When to invoke

- About to write a new class hierarchy (will you reach for Singleton / Strategy / Factory / Composite?)
- About to design a service layer / data access layer / application boundary
- About to add resilience (retry, breaker, bulkhead, timeout) — order matters; the catalog has the right order
- About to design an offline-survivable pipeline (queue, outbox, CRDT, sync engine)
- About to add an AI feature (RAG, ReAct, tool-use, structured output, semantic search)
- About to pick a tech (broker, real-time transport, vector DB, identity provider) — the catalog has the constraints that rule out wrong choices (no Azure Service Bus, no cloud-only stuff)

## When NOT to invoke

- Trivial line-of-code change
- Bug fix in existing code that already uses a pattern correctly
- Reading code (skill is for designing / writing)

## Hard rules

1. **Search before designing.** `rote dp find "<problem description>"` or `dp.search()` via MCP. Distance < 0.7 → use it. Distance < 1.0 → read it and decide whether to apply.
2. **Search before writing boilerplate.** `rote snippet find "<one-line description>"` returns parameterized templates with `${PLACEHOLDER}` tokens. `rote snippet expand <slug> --VAR=value ...` substitutes and emits the rendered code. Use the canonical shape; don't regenerate from training data.
3. **Search before picking a stack.** `rote stack find "<problem + constraints>"` returns recorded experiments (success / partial / failure) so we don't relearn the hard way. Pay attention to `failure` outcomes; the lesson is in the `what_didnt` + `when_to_avoid` sections.
4. **Cite the pattern / snippet in code comments.** A class that implements Strategy should say `// Strategy for X` in its header. A method assembled from `snippet/polly-named-policy-registration` should mention the slug. This is how the next reader finds the catalog entry.
5. **Use `dp use` / `tech use` / `snippet use` / `stack use`** when you actually apply something. Tracks what's load-bearing vs documented-only.
6. **Cross-reference the technology catalog** for "what to implement this with." Patterns answer "what to build"; technologies answer "with what"; snippets answer "how exactly"; stacks answer "have we tried this combo and what came of it."
7. **Don't pick a technology by name recognition.** Search by your CONSTRAINTS (offline-capable, self-hostable, open-source). The catalog flags cautionary entries (Azure Service Bus — cloud-only, ruled out for Acme) AND the stacks catalog has a record (`azure-service-bus-for-offline-considered-and-rejected`) explaining why.

## Decision flow

```
about to write pattern-shaped code?
├── rote dp find "<one-line problem description>"
│   ├── distance < 0.7  →  use the canonical shape; cite in comments
│   ├── distance < 1.0  →  read it; decide between using-as-is or extending
│   └── no match        →  the pattern may be missing.  Write it; THEN seed
│                          a new design-patterns/<category>/<slug>.md
│                          so future-Claude has it.
├── need a concrete tech to implement?  →  rote tech find "<constraints>"
│                                          ALWAYS read when_not_to_use + limitations
│                                          to confirm the tech fits THIS stack
│                                          (look for offline-capable / self-hosted
│                                          tags if you need offline survival)
└── after applying:
    rote dp use <slug>    # bumps use_count; signals "this is load-bearing"
    rote tech use <slug>  # ditto for tech selections
```

## Catalog surface

### Design Patterns (5 categories)

- **classical** — GoF + adjacent: singleton, factory-method, abstract-factory, builder, strategy, observer, decorator, adapter, composite, chain-of-responsibility, command, template-method
- **architectural** — clean-architecture, hexagonal-ports-adapters, repository-pattern, service-layer, cqrs, event-sourcing, domain-driven-aggregate, mvc-mvp-mvvm
- **resilience** — circuit-breaker, retry-with-exponential-backoff-jitter, bulkhead, timeout-and-deadline, fallback, health-check-readiness-liveness, idempotency-token, queue-based-load-leveling
- **offline** — local-first-architecture, outbox-pattern, crdt, offline-queue-bulkhead, optimistic-ui, eventually-consistent-replication
- **ai** — rag-retrieval-augmented-generation, react-reasoning-and-acting, tool-use-function-calling, structured-output-with-schema, semantic-search-with-embeddings, mcp-aggregator-proxy, skill-based-prompting, prompt-caching, multi-agent-orchestration

### Technologies (mapped to patterns + tagged)

- **messaging** — rabbitmq, mosquitto, azure-service-bus (← cautionary: no offline)
- **realtime** — signalr, socket-io, webrtc
- **resilience-library** — polly
- **ai-infrastructure** — ollama, sglang
- **vector-db** — sqlite-vec
- **database** — postgresql, sqlite
- **identity** — authentik
- **mcp-infrastructure** — metamcp
- **orchestration** — docker-compose

Tags include: `offline-capable`, `self-hosted`, `cloud-only`, `vendor-locked`, `open-source`.

## API surface

### Design patterns

```bash
rote dp find "<query>" [--category CAT]
rote dp list [--category CAT]
rote dp show <slug>
rote dp use <slug> [--notes TEXT]
```

### Technologies

```bash
rote tech find "<query>" [--category CAT]
rote tech list [--category CAT] [--tag TAG]
rote tech show <slug>
rote tech use <slug> [--notes TEXT]
```

### Snippets

```bash
rote snippet find "<query>" [--language LANG]
rote snippet list [--language LANG]
rote snippet show <slug>                       # body + placeholders
rote snippet expand <slug> --VAR1=value --VAR2=value
rote snippet use <slug> [--notes TEXT]
```

### Stacks

```bash
rote stack find "<query>" [--outcome success|failure|partial|mixed]
rote stack list [--outcome ...]
rote stack show <slug>                         # what worked / didn't / reuse / avoid
rote stack use <slug> [--notes TEXT]
```

### Commands

```bash
rote cmd find "<query>" [--family FAM]         # building-block console commands
rote cmd list [--family FAM] [--platform PLATFORM]
rote cmd show <slug>                           # invocation + gotchas + flags + equivalents
rote cmd use <slug> [--notes TEXT]
```

### MCP tools (18 total in these four catalogs)

Design patterns: `find_design_pattern`, `list_design_patterns`, `show_design_pattern`, `log_design_pattern_use`
Technologies:    `find_technology`, `list_technologies`, `show_technology`, `log_technology_use`
Snippets:        `find_snippet`, `list_snippets`, `show_snippet`, `expand_snippet`, `log_snippet_use`
Stacks:          `find_stack`, `list_stacks`, `show_stack`, `log_stack_use`

## Adding a new pattern or technology

Drop a markdown file under `/path/to/rote/design-patterns/<category>/<slug>.md` or `/path/to/rote/technologies/<category>/<slug>.md`. Frontmatter:

```markdown
---
slug: my-pattern
name: My Pattern
category: classical
intent: One-line problem statement
references: source citations
---

# When to use
...

# When NOT to use
...

# Structure
...

# Example
...

# Relationships
links to other patterns: [[strategy]], composes with [[circuit-breaker]]
```

For technologies, swap `Structure / Example / Relationships` for `Limitations / Cost / Alternatives` and add `implements_patterns: <comma-separated slugs>` to the frontmatter.

The API auto-indexes on next list/search. Re-seed via `scripts/seed-design-patterns-and-technologies.py` if you want to restore the canonical initial set from this repo.

## Cross-reference

- [[rote]] — sibling skill for reusable scripts
- [[secret-handling]] — don't put secret values in tool calls; never in pattern examples either
- [[chronicle]] — record patterns applied in §3 of post-mortems so the catalog grows
- See anti-patterns `tmp-script-one-shot` and `code-rewrite-line-by-line` for the failure modes this skill prevents on the SCRIPT side; the pattern catalog prevents the same on the DESIGN side.
