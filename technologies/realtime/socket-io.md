---
slug: socket-io
name: Socket.IO
category: realtime
implements_patterns: observer, rpc-over-websocket
tags: self-hosted, node-native, offline-capable-with-fallback, open-source
references: https://socket.io/
---

# When to use
Node.js backend with realtime needs — Socket.IO is the de facto standard.

You want WebSocket + automatic fallback (long polling) for compatibility with old proxies / corporate networks.

You want room-based broadcast, ack callbacks, namespace isolation.

# When NOT to use
You're on .NET — SignalR is the local equivalent.

You can stick to raw WebSockets — less framework lock-in.

Browser-only — and the long-polling fallback isn't needed — it's overhead.

# Limitations
- Socket.IO protocol is NOT just WebSockets — clients and servers must speak Socket.IO specifically.
- Scale-out requires a Redis adapter (or similar).
- v3/v4 protocol changes have caused upgrade pain.

# Cost
Free open-source.  Server compute per concurrent connection is modest.

# Alternatives
Raw WebSockets (`ws`, `uWebSockets.js`).  SignalR (if you can move to .NET).  Phoenix Channels.  WebSocket Subprotocols (binary + wsSerial pattern Betaflight uses).
