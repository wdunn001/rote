---
slug: command
name: Command
category: classical
intent: Encapsulate a request as an object — parameters, receiver, action — so it can be queued, logged, undone, replayed
references: GoF Command
---

# When to use
Operations need to be persisted (audit log, event sourcing, undo/redo).

Operations need to be deferred (queue, schedule, batch).

You want to send operations over a wire (a wire format = serialized commands).

Examples: DroneCommand discriminated-union in mz packages, CoT activity tracker, replay-able CQRS commands.

# When NOT to use
Operations are synchronous, never persisted, never undone — direct method calls are simpler.

You're using Command as a fancy lambda — just use a lambda.

# Structure
Command interface declares Execute().  Concrete commands hold all parameters + reference to receiver.  Invoker triggers execute (synchronously or queued).

# Example
```typescript
type DroneCommand =
  | { kind: 'arm' }
  | { kind: 'flyToHere', target: GeoPoint, ned?: NedOffset }
  | { kind: 'follow', leader: SystemId, distance?: number }
  | { kind: 'rtl' };

// Wire-format = serialized command; replay = re-execute
function execute(cmd: DroneCommand) { /* discriminated dispatch */ }
```

# Relationships
Foundation of CQRS (commands separate from queries).  Foundation of event-sourcing (the event log IS the sequence of executed commands).  Pairs with outbox-pattern for reliable cross-system command propagation.
