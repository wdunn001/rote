---
slug: chain-of-responsibility
name: Chain of Responsibility
category: classical
intent: Pass a request along a chain of handlers; each handler decides whether to handle it or forward
references: GoF Chain of Responsibility
---

# When to use
Multiple potential handlers and the right one is determined at runtime: middleware, request routing, fallback chains, message routing.

The chain order matters and handlers know nothing of each other.

Examples: c2_router in mz-pid-tuner (try DeviceA MQTT → fall back to WiFi-TCP → return Unreachable), ASP.NET middleware pipeline.

# When NOT to use
Exactly one handler will handle the request — use Strategy instead.

The chain is short (2 handlers) — direct if/else is clearer.

Handlers need to coordinate or share state — use mediator.

# Structure
Handler interface declares Handle(request).  Each ConcreteHandler decides: handle it, transform-and-pass-on, or pass-on unchanged.  Last handler returns a default or raises.

# Example
```cpp
// mz-pid-tuner c2_router::send() walks Strategies best-to-worst
SendResult C2Router::send(PeerIdentity peer, const uint8_t* data, size_t n) {
    for (auto& strategy : strategies_) {
        SendResult r = strategy.send(peer, data, n);
        if (r != SendResult::Unreachable) return r;
    }
    return SendResult::Unreachable;
}
```

# Relationships
Pairs with strategy (each handler IS a strategy).  Used in routers, middleware, fallback policies.  Often composed with circuit-breaker (open breaker fast-fails to next handler).
