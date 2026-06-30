---
slug: observer
name: Observer
category: classical
intent: Define a one-to-many dependency so when one object changes state, dependents are notified automatically
references: GoF Observer; React state model; SignalR hubs
---

# When to use
Reactive UIs: state change drives view re-render.

Domain event broadcasting: a sale completed → notify inventory, billing, audit, analytics independently.

Realtime subscriptions: a SignalR hub broadcasts to N clients; an MQTT topic publishes to N subscribers.

# When NOT to use
The notification is a one-shot — use a callback / Promise.

Observers form cycles or need ordered execution — use a proper event-bus with ordering guarantees.

You actually need persistent subscription semantics across crashes — use queue-based / outbox patterns.

# Structure
Subject maintains a list of Observers.  Observers register / unregister.  On state change, Subject calls Update on each observer.

# Example
```csharp
// SignalR is observer at scale — Update = SendAsync.
public class TakActivityHub : Hub {
    public async Task SubscribeCompany(string companyId) {
        await Groups.AddToGroupAsync(Context.ConnectionId, $"company:{companyId}");
    }
}

// Publisher fan-out:
await _hub.Clients.Group($"company:{cid}").SendAsync("cot.received", evt);
```

# Relationships
Foundation of pub/sub (observer = in-process pub/sub).  Pairs with mediator (observer is point-to-point; mediator centralizes routing).  Often composed with circuit-breaker for protecting observers from a flaky subject.
