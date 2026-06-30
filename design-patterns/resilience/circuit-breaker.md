---
slug: circuit-breaker
name: Circuit Breaker
category: resilience
intent: Stop calling a failing dependency for a cooldown period so the dependency can recover and callers fail fast
references: Michael Nygard 'Release It!'; Polly docs
---

# When to use
Synchronous calls to a dependency that can degrade or fail (HTTP API, MQTT broker, database).

The cost of repeatedly attempting calls during an outage is high (latency, resource exhaustion, cascading failure).

You want fast failure during outages instead of slow timeouts.

# When NOT to use
Internal calls in a single process — circuit breakers add latency tracking + state machine; not worth it.

Backends that are designed to handle infinite retries (idempotent enqueues) — just retry.

You haven't tuned the threshold + cooldown — defaults often produce more harm than good.

# Structure
States: Closed (calls flow), Open (calls fast-fail), Half-Open (a probe call decides whether to close).  Threshold = consecutive failures or failure rate.  Cooldown = how long Open lasts.

# Example
```csharp
services.AddHttpClient<IFooClient, FooClient>()
    .AddPolicyHandler(Policy<HttpResponseMessage>
        .Handle<HttpRequestException>()
        .CircuitBreakerAsync(
            handledEventsAllowedBeforeBreaking: 5,
            durationOfBreak: TimeSpan.FromSeconds(30)));
```

# Relationships
Foundation of resilient systems.  Pairs with retry-with-exponential-backoff-jitter (retry then breaker, not breaker then retry).  Pairs with fallback (when breaker is open, fallback fires).  Pairs with bulkhead (per-dependency isolation).
