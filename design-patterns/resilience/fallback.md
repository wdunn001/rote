---
slug: fallback
name: Fallback
category: resilience
intent: Substitute a degraded-but-useful response when the primary path fails
references: Polly Fallback; 'Release It!'
---

# When to use
A degraded answer is still useful: cached value, default, last-known-good, simplified UI.

The primary fails for a reason the fallback isn't subject to (independent failure modes).

The user experience is graceful degradation, not error.

# When NOT to use
There's no honest fallback — returning empty / null / stale is worse than failing visibly.

The fallback masks a real bug — alerting + visible failure surface the issue faster.

The fallback diverges from the primary in a way that creates split-brain.

# Structure
Primary call → on failure → fallback path.  Fallback is documented as 'degraded mode' so it's never mistaken for normal.

# Example
```csharp
services.AddHttpClient<IWeatherClient, WeatherClient>()
    .AddPolicyHandler(Policy<HttpResponseMessage>
        .Handle<Exception>()
        .FallbackAsync(
            fallbackAction: ct => Task.FromResult(_lastKnownGood.Value),
            onFallbackAsync: ex => _metrics.Increment("weather.fallback.fired")));
```

# Relationships
Pairs with circuit-breaker (when breaker is open, fallback fires).  Pairs with graceful-degradation (system-level fallback).
