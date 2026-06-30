---
slug: idempotency-token
name: Idempotency Token
category: resilience
intent: Make a non-idempotent operation safely retryable by deduplicating on a client-supplied unique token
references: Stripe's idempotency-key header docs; RFC draft-ietf-httpapi-idempotency-key-header
---

# When to use
Operations with side effects you cannot undo: payment authorization, message dispatch, drone command issuance.

You want to allow retries (network blip, timeout) without double-actions.

Network is unreliable enough that the client genuinely doesn't know if its first attempt succeeded.

# When NOT to use
The operation is already idempotent by nature (PUT, conditional update).

You're not actually deduplicating — the token is decorative.  Real dedup needs a unique-key constraint + 'already exists' handling.

# Structure
Client generates a UUID per logical operation.  Server stores (token → result) in a dedup cache.  Repeated POST with same token returns the cached result (not a re-execution).  TTL bounds the cache.

# Example
```csharp
public async Task<CommandResult> Issue(IssueRequest req, string idempotencyKey) {
    var cached = await _dedup.GetAsync(idempotencyKey);
    if (cached != null) return cached;

    var result = await DoIssue(req);
    await _dedup.SetAsync(idempotencyKey, result, ttl: TimeSpan.FromHours(24));
    return result;
}
```

# Relationships
Foundation of safe retry.  Pairs with retry-with-exponential-backoff-jitter.  Pairs with outbox-pattern (outbox row IS an idempotency token for downstream delivery).
