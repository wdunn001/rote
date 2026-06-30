---
slug: offline-queue-bulkhead
name: Offline Queue (Bulkhead between Online + Offline)
category: offline
intent: Persistent local queue that decouples production from delivery so producers never block on the network
references: Acme apps/companion packages/offline-queue
---

# When to use
Devices that periodically lose connectivity (companion app on a phone, drone with cellular dropouts).

Multiple producers feeding multiple delivery channels: telemetry → device-ingest, CoT → TAK fan-out, blackbox → upload.  One queue per channel = independent retry budgets.

You need at-least-once delivery across crashes (the queue is on disk).

# When NOT to use
Volatile data that's worthless if delivered late — don't queue it; drop on disconnect.

The queue size could grow unbounded — set a retention policy or risk filling the disk.

# Structure
Each event class has its own queue (independent backpressure).  Persistent (sqlite, plain file, embedded LMDB).  Drainer task per queue: reads next, sends, marks sent on ack, retries on failure.

# Example
The Acme companion's packages/offline-queue is exactly this.  Three streams: pilot telemetry, CoT events, swarm-state — each independently queued + drained.  See arch-fc-param-pipeline.

# Relationships
Pairs with outbox-pattern (queue persisted in a transactional DB).  Pairs with bulkhead (per-stream isolation).  Foundation of local-first-architecture.
