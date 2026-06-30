---
slug: polly-named-policy-registration
name: Polly named-policy registration
language: csharp
applies_patterns: circuit-breaker, retry-with-exponential-backoff-jitter, timeout-and-deadline, bulkhead
applies_technologies: polly
references: 
---

# When to use
Every outbound HttpClient in a .NET app needs a named Polly policy.  This
snippet registers a typed HttpClient + a composed policy stack:
timeout(individual) → retry → circuit-breaker → bulkhead.

# When NOT to use
You're using Microsoft.Extensions.Http.Resilience (.NET 8+) — has a more
modern API and is the recommended replacement.

You're using HttpClientFactory's basic resilience — Polly composition gives
you more control.

# Placeholders
- CLIENT_INTERFACE: the IFooClient interface name (example: IGraphEmailClient)
- CLIENT_TYPE: the concrete implementation type (example: GraphEmailClient)
- POLICY_NAME: kebab-case named policy for the registry (example: graph-email)
- BASE_ADDRESS: the upstream base URL (example: https://graph.microsoft.com)
- RETRY_COUNT: max retries before giving up (example: 4)
- BREAKER_THRESHOLD: consecutive failures before breaker opens (example: 5)
- BREAKER_DURATION_SEC: circuit-breaker cooldown seconds (example: 30)
- MAX_PARALLELIZATION: bulkhead concurrency cap (example: 10)
- TIMEOUT_SEC: per-attempt timeout seconds (example: 15)

# Snippet
```csharp
// ${POLICY_NAME} — outbound calls to ${BASE_ADDRESS}
services.AddHttpClient<${CLIENT_INTERFACE}, ${CLIENT_TYPE}>(c =>
    {
        c.BaseAddress = new Uri("${BASE_ADDRESS}");
    })
    .AddPolicyHandler(Policy<HttpResponseMessage>
        .Handle<HttpRequestException>()
        .OrResult(r => (int)r.StatusCode >= 500)
        .WaitAndRetryAsync(${RETRY_COUNT}, attempt =>
            TimeSpan.FromMilliseconds(Math.Min(60_000,
                200 * Math.Pow(2, attempt) + Random.Shared.Next(0, 250)))))
    .AddPolicyHandler(Policy<HttpResponseMessage>
        .Handle<HttpRequestException>()
        .CircuitBreakerAsync(${BREAKER_THRESHOLD}, TimeSpan.FromSeconds(${BREAKER_DURATION_SEC})))
    .AddPolicyHandler(Policy.TimeoutAsync<HttpResponseMessage>(${TIMEOUT_SEC}))
    .AddPolicyHandler(Policy.BulkheadAsync<HttpResponseMessage>(
        maxParallelization: ${MAX_PARALLELIZATION}, maxQueuingActions: 50));
```

# Example expansion
graph-email, authentik, mqtt-publish in Acme.  See CLAUDE.md 'Polly named-policy convention'.
