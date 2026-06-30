---
slug: event-sourcing
name: Event Sourcing
category: architectural
intent: Store the sequence of state CHANGES, not the current state; rebuild state by replaying events
references: Greg Young; Vaughn Vernon 'Implementing DDD'
---

# When to use
Audit is the product: regulatory systems, financial ledgers, blackbox flight recorders.

You need to ask 'what was the state at time T?' as a first-class query.

Multiple projections need to be derivable from the same source of truth.

# When NOT to use
The current state IS what matters and the history is uninteresting.

You can't bound the event volume (millions per second with no archival path) — event sourcing under load needs serious infra.

# Structure
Append-only event log.  Aggregates rebuild from events.  Snapshots accelerate replay.  Projections subscribe to the log and materialize views.

# Example
```typescript
type DroneEvent =
  | { kind: 'DroneEnrolled', t: Date, droneId: string, fingerprint: string }
  | { kind: 'CommandIssued', t: Date, cmd: DroneCommand }
  | { kind: 'TelemetryReceived', t: Date, sample: TelemetrySample };

class Drone {
  static fromHistory(events: DroneEvent[]): Drone {
    const d = new Drone();
    for (const e of events) d.apply(e);
    return d;
  }
  apply(e: DroneEvent) { /* fold */ }
}
```

# Relationships
Pairs with CQRS (events drive projections).  Adjacent to outbox-pattern (events as messages).  The blackbox use case in mz-pid-tuner is event-sourcing in the small.
