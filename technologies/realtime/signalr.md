---
slug: signalr
name: SignalR
category: realtime
implements_patterns: observer, rpc-over-websocket
tags: self-hosted-or-managed, .net-native, offline-capable-with-fallback, open-source
references: https://learn.microsoft.com/aspnet/core/signalr/
---

# When to use
.NET backend pushing realtime updates to web/mobile clients (decode progress, analysis updates, CoT activity).

You want automatic transport fallback (WebSocket → SSE → long polling) — SignalR handles it.

You want automatic reconnect, group broadcast, per-user targeting.

Acme uses SignalR for /hubs/notifications, /hubs/company-chat, /hubs/tak-activity.

# When NOT to use
Non-.NET backend — Socket.IO or raw WebSockets are more portable.

You don't want clients tightly coupled to a .NET hub class shape.

You need horizontal scale-out across many backends — SignalR works with Redis/Service Bus backplane, but configure carefully.

# Limitations
- Best with .NET clients; JS clients work well but Java/Python/Go are second-class.
- Scale-out requires a backplane (Redis, Service Bus, or Azure SignalR Service) — adds operational complexity.
- Auto-fallback transports have different feature sets; long polling is feature-poor.

# Cost
Open-source server; runs alongside your API.  Azure SignalR Service: ~$1/day per 1k concurrent connections — convenient but cloud-only.

# Alternatives
Socket.IO (Node-native; cross-language clients good).  Raw WebSockets + your own protocol (max control).  Phoenix Channels (Elixir-native, very high scale).  Server-Sent Events (one-way only; simpler).
