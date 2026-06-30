---
slug: domain-driven-aggregate
name: Aggregate (DDD)
category: architectural
intent: Cluster of domain objects treated as a single transactional unit, with one root that enforces invariants
references: Vaughn Vernon 'Implementing DDD'
---

# When to use
Domain has complex invariants spanning multiple entities (a Swarm + its FormationPolicy + its FleetHome must stay consistent).

You want clear transactional boundaries (the aggregate is what gets saved atomically).

Concurrent updates need predictable conflict semantics — the aggregate is the unit of optimistic locking.

# When NOT to use
Anemic domain — your 'aggregates' are just DTOs with no behavior.  Aggregates are useless if entities don't enforce invariants.

You're forcing a small operation into a huge aggregate just because — split it.  Smaller aggregates are better.

# Structure
Aggregate root is the only externally-visible entity.  Internal entities and value objects are accessed only via the root.  All mutations go through the root.  Persistence is per-aggregate, atomically.

# Example
```csharp
public class Swarm : AggregateRoot {  // root
    private readonly List<DroneId> _members = new();
    public FleetHome Home { get; private set; }  // internal entity
    public FormationPolicyId ActiveFormation { get; private set; }

    public void FormUp() {  // mutation goes through root
        EnsureCanFormUp();  // invariant
        Home.Activate();
        ActiveFormation = ...;
        AddDomainEvent(new SwarmFormedUp(Id));
    }
}
```

# Relationships
Foundation of DDD.  Pairs with repository-pattern (one repo per aggregate).  Pairs with composite (Swarm IS a Composite<Drone> conceptually).
