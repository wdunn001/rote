---
slug: retry-with-exponential-backoff-jitter
name: Retry with Exponential Backoff + Jitter
category: resilience
intent: Retry transient failures with growing delays, randomized to avoid thundering herd
references: Polly; AWS Architecture Blog 'Exponential backoff and jitter'
---

# When to use
Transient failures (network blip, brief overload, conflict that resolves under retry).

The operation is idempotent OR you have an idempotency token.

The downstream can absorb retries (you're not making the problem worse).

# When NOT to use
The operation isn't idempotent and there's no token — retrying double-charges, double-sends.

You're retrying inside a retry (compounding exponentials = surprise outage).

The failure is permanent (4xx, schema mismatch) — don't retry 4xx.

You're not jittering — synchronized retries trigger thundering herd.

# Structure
Attempt → on transient failure, wait base * 2^attempt + random(0, jitter) → retry up to max attempts.  Cap the max delay.  Distinguish transient vs permanent failures.

# Example
```csharp
services.AddHttpClient<IFooClient, FooClient>()
    .AddPolicyHandler(Policy<HttpResponseMessage>
        .Handle<HttpRequestException>()
        .OrResult(r => (int)r.StatusCode >= 500)
        .WaitAndRetryAsync(
            retryCount: 4,
            sleepDurationProvider: i =>
                TimeSpan.FromMilliseconds(Math.Min(60_000,
                    200 * Math.Pow(2, i) + new Random().Next(0, 250)))));
```

# Relationships
Layer ORDER: retry-INSIDE circuit-breaker, not outside (breaker bounds total work).  Pairs with idempotency-token.  Pairs with timeout (each retry attempt has its own).
