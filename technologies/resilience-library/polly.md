---
slug: polly
name: Polly (.NET resilience)
category: resilience-library
implements_patterns: retry-with-exponential-backoff-jitter, circuit-breaker, bulkhead, timeout-and-deadline, fallback
tags: open-source, .net-only, mature
references: https://www.thepollyproject.org/; CLAUDE.md 'Polly named-policy convention' in acme
---

# When to use
ANY outbound HTTP call from a .NET app.

Any external dependency where transient failures are possible.

You want named policies that compose (retry inside circuit-breaker inside bulkhead).

Acme uses Polly named-policy convention — see CLAUDE.md 'Polly named-policy convention.'

# When NOT to use
You're not on .NET — Resilience4j (Java), Hystrix (legacy Java), failsafe-go.  Each platform has its own.

You're using Polly without configuration — defaults are conservative; tune to your dependency.

You wrap policies around fire-and-forget calls without using cancellation — policies can't cancel what you didn't tell them to.

# Limitations
- .NET-only; cross-platform consistency requires equivalent libraries on other stacks.
- Composition order matters: retry inside breaker, NOT breaker inside retry.
- Policy registry can get unwieldy — name conventions matter.

# Cost
Free open-source.  Tiny runtime overhead.

# Alternatives
Resilience4j (Java).  failsafe-go (Go).  Cockatiel (Node — Polly port).  Hand-rolled (don't — get the order wrong and you cascade failures).
