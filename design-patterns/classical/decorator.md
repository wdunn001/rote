---
slug: decorator
name: Decorator
category: classical
intent: Add behavior to an object dynamically by wrapping it, without modifying the wrapped type
references: GoF Decorator
---

# When to use
You want to compose orthogonal behaviors at runtime: logging + retry + cache + rate-limit around the same call.

The wrapped object shouldn't know it's being decorated (the wrapper preserves the original interface).

Examples: HttpClient handlers in .NET, middleware in web frameworks, Polly policy wrappers.

# When NOT to use
Behaviors are static and known at design time — use inheritance or direct composition.

The decorator changes the interface (now it's an adapter, not a decorator).

# Structure
Decorator implements the same interface as the wrapped Component; holds a reference to it; delegates to it + adds behavior before/after.

# Example
```csharp
// HttpClient handler chain — each handler decorates the next.
services.AddHttpClient<IFooClient, FooClient>()
    .AddHttpMessageHandler<RetryHandler>()
    .AddHttpMessageHandler<CircuitBreakerHandler>()
    .AddHttpMessageHandler<LoggingHandler>();
```

# Relationships
Foundation of middleware / pipeline patterns.  Pairs with chain-of-responsibility (which routes; decorator wraps).  Often used to implement resilience patterns (circuit-breaker, retry, timeout).
