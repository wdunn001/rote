---
slug: adapter
name: Adapter
category: classical
intent: Convert one interface into another that clients expect
references: GoF Adapter; Cockburn 'Hexagonal Architecture'
---

# When to use
Wrapping a third-party library so it implements YOUR interface (so you can swap libraries later).

Bridging legacy code into modern interfaces.

Implementing a port (Domain interface) with concrete tech (Infrastructure) — every Infrastructure adapter is the Adapter pattern.

# When NOT to use
The interfaces are already compatible — direct call, no wrapper.

You're adapting MANY methods with deep mismatch — refactor toward a custom interface instead of bridging.

# Structure
Adapter holds a reference to the Adaptee and implements the Target interface by translating calls.

# Example
```csharp
// Infrastructure adapter wrapping Graph API to satisfy the Domain IEmailSender port.
public class MicrosoftGraphEmailSender : IEmailSender {
    private readonly GraphServiceClient _graph;
    public Task SendAsync(EmailMessage m, CancellationToken ct) =>
        _graph.Users[...].SendMail.PostAsync(GraphFor(m), cancellationToken: ct);
}
```

# Relationships
Foundation of hexagonal-ports-adapters.  Different from decorator (adapter changes interface; decorator preserves it).
