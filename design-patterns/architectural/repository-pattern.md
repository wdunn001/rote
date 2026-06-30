---
slug: repository-pattern
name: Repository
category: architectural
intent: Encapsulate data access behind a collection-like interface so domain code doesn't depend on storage tech
references: Fowler PEAA; DDD Blue Book
---

# When to use
Domain has aggregates (DDD) and you want the storage tech to be a swappable detail.

Multiple storage backends might be used (test in-memory, prod Postgres, edge SQLite).

You want queries expressed in domain terms ('drones in fleet X') not SQL.

# When NOT to use
Repository becomes a thin wrapper over an ORM — you've added a layer with no benefit.  Just use the ORM.

You're hiding the ORM but every consumer drops to raw SQL anyway — accept the leak or change the design.

# Structure
Repository interface in Domain.  EF/Mongo/Dapper implementation in Infrastructure.  Methods are domain-language: AddDrone, GetByFleet, FindActiveByTenant.

# Example
```csharp
public interface IDroneRepository {
    Task<Drone?> GetAsync(DroneId id, CancellationToken ct);
    Task<IReadOnlyList<Drone>> ListByFleetAsync(FleetId fleet, CancellationToken ct);
    Task AddAsync(Drone d, CancellationToken ct);
    Task SaveChangesAsync(CancellationToken ct);
}
```

# Relationships
Lives at the Application/Infrastructure boundary in clean-architecture.  Pairs with unit-of-work (SaveChangesAsync = UoW commit).  Foundation of aggregate-root persistence.
