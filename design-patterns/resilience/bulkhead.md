---
slug: bulkhead
name: Bulkhead
category: resilience
intent: Isolate resource pools per dependency so a slow dependency doesn't drain everything
references: Michael Nygard 'Release It!'; Polly Bulkhead
---

# When to use
You have multiple downstream dependencies sharing one pool (thread pool, connection pool, queue) — a slow one can starve fast ones.

You want to bound concurrent calls to a specific dependency so it can't overwhelm itself.

Background work shouldn't be able to starve interactive work.

# When NOT to use
You have only one downstream and one workload class — bulkhead is unnecessary.

The 'bulkhead' isolates things that genuinely share state — you've added latency without isolation benefit.

# Structure
Per-dependency thread pool / semaphore / connection pool.  Hard cap on concurrent operations.  Excess work queues, throttles, or fast-fails.

# Example
```csharp
services.AddHttpClient<IFooClient, FooClient>()
    .AddPolicyHandler(Policy.BulkheadAsync<HttpResponseMessage>(
        maxParallelization: 10,
        maxQueuingActions: 50,
        onBulkheadRejectedAsync: ctx => { /* log + fast fail */ }));
```

# Relationships
Pairs with circuit-breaker (per-dependency isolation).  Pairs with rate-limiter (bound rate; bulkhead bounds concurrency).  Foundation of the Acme companion offline-queue pattern.
