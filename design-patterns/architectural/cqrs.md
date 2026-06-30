---
slug: cqrs
name: CQRS (Command Query Responsibility Segregation)
category: architectural
intent: Split read and write models so each can be optimized independently
references: Greg Young CQRS Documents
---

# When to use
Reads and writes have wildly different shapes / load profiles (analytics dashboard vs transactional writes).

The write model is a strict aggregate (consistency), reads are flexible projections (eventual consistency OK).

Multiple read shapes for the same data (per-user feed, per-tenant report, full-text index) all derived from one write model.

# When NOT to use
Simple CRUD where reads + writes share the same model.  CQRS triples complexity for no value.

You don't have a way to keep the read projection in sync with writes (no event log, no triggers).

# Structure
Commands mutate state via the write model (the aggregate / repository).  Queries read from denormalized projections.  An event/outbox propagates writes to projections.  Reads are typically eventually consistent.

# Example
```csharp
// Write side
public class IssueDroneCommandHandler {
    public async Task Handle(DroneCommand cmd) {
        var drone = await _repo.GetAsync(cmd.DroneId);
        drone.Apply(cmd);
        await _repo.SaveChangesAsync();
        await _outbox.PublishAsync(new DroneCommandIssued(cmd));
    }
}

// Read side — separate denormalized projection
public class DroneCockpitQuery {
    public async Task<DroneCockpitView> Get(DroneId id) =>
        await _readDb.GetByDroneIdAsync(id);  // not the same DB; not the same shape
}
```

# Relationships
Pairs with event-sourcing (writes = events, projections = read models).  Pairs with outbox-pattern.  Foundation of read-replica / search-index architectures.
