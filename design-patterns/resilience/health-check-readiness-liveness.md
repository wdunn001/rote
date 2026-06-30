---
slug: health-check-readiness-liveness
name: Health Check / Readiness / Liveness
category: resilience
intent: Distinct probes signaling whether the process is alive vs ready to serve traffic vs which dependencies are degraded
references: Kubernetes probes; ASP.NET HealthChecks
---

# When to use
Containerized / orchestrated environments where the platform decides when to restart / route traffic.

Multi-dependency apps where you need to distinguish 'I crashed' from 'broker is down but ingest still works'.

Operations needs a fast probe for monitoring + a deep probe for diagnostics.

# When NOT to use
Single static binary on a single host with no orchestration — overhead.

Probes that hit downstream services synchronously without timeout — the probe becomes a DoS vector.

# Structure
Liveness (/health/live): is the process running and serving HTTP at all?  Restart if not.
Readiness (/health/ready): all hard dependencies up?  Route traffic if so.  Returns 'degraded' (200) when soft deps are down but service still useful.
Details (/health/details): full diagnostic — per-dep timings, last error, breaker state.  Auth-gated.

# Example
```csharp
services.AddHealthChecks()
    .AddNpgSql(_pg, tags: new[] { "ready" })
    .AddRabbitMQ(_amqp, tags: new[] { "ready", "degradable" })
    .AddCheck<MqttBrokerCheck>("mqtt", tags: new[] { "degradable" });

app.MapHealthChecks("/health/live", new HealthCheckOptions { Predicate = _ => false });
app.MapHealthChecks("/health/ready", new HealthCheckOptions { Predicate = c => c.Tags.Contains("ready") });
```

# Relationships
Pairs with circuit-breaker (breaker state surfaces in /details).  Foundation of platform-driven self-healing.  Acme uses this — see CLAUDE.md Health endpoints table.
