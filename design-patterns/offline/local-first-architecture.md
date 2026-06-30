---
slug: local-first-architecture
name: Local-First Architecture
category: offline
intent: Data lives primarily on the user's device; sync to cloud is optional and best-effort
references: Ink & Switch 'Local-first software'; Martin Kleppmann
---

# When to use
Users work disconnected (field tech, drone pilots in flight, traveling sales, anyone with flaky connectivity).

Latency-sensitive UI (typing in a doc, drawing on a map) — round-trips to a server feel laggy.

Multi-device per user where each device should keep working independently.

# When NOT to use
Data is fundamentally shared real-time across users (a multiplayer game state).

Data is so large it can't fit on the device (cloud-native is the only option).

Strict server-side authorization is the source of truth (banking transactions).

# Structure
Local DB on device is the source of truth FOR THE USER.  Sync engine bidirectionally reconciles with a cloud DB when connectivity is available.  Conflicts are resolved deterministically (CRDT, LWW, vector clocks).

# Example
The Acme companion app: telemetry queued locally via offline-queue, drained to /devices/ingest when connected.  Drone firmware: device commands cached on SD card, pulled back to server when connected.  See arch-fc-param-pipeline memory entry.

# Relationships
Pairs with crdt (the merge math).  Pairs with outbox-pattern (queued mutations).  Pairs with sync-engine (bidirectional reconciliation).  Foundation of Acme offline-survivable pipeline.
