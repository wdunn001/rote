---
slug: timeout-and-deadline
name: Timeout + Deadline
category: resilience
intent: Bound how long any individual call can take; cancel and free resources if exceeded
references: Polly Timeout; gRPC deadlines
---

# When to use
EVERY synchronous external call — without exception.  No timeout = guaranteed eventual hang.

Long-running operations that should give up if upstream changes (user navigated away, request cancelled).

End-to-end deadlines: the caller has 30s total budget; pass that down so each step knows how much remains.

# When NOT to use
Timeout shorter than the operation's natural latency — guaranteed false-positive failures.

Timeout without a circuit breaker — you fail fast on each call but keep slamming the downstream.

Cancellation tokens that no one observes — paper timeout, real hang.

# Structure
Total time budget for an operation.  Propagated via CancellationToken / context.WithDeadline.  Each layer reads its remaining budget and shortens its own.

# Example
```csharp
using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(30));
await client.SendAsync(request, cts.Token);
// Combined with Polly timeout policy for redundancy:
.AddPolicyHandler(Policy.TimeoutAsync<HttpResponseMessage>(15));
```

# Relationships
Pairs with circuit-breaker (timeout failures feed the breaker's count).  Pairs with retry (each attempt has its own timeout; retry budget < deadline).  Pairs with bulkhead (timeouts free pooled resources back).
