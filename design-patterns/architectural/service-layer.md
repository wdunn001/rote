---
slug: service-layer
name: Service Layer
category: architectural
intent: A layer of application services that orchestrate domain logic and infrastructure for a use case
references: Fowler PEAA; Acme uses this pattern throughout Acme.Application
---

# When to use
Use cases involve multiple domain entities + side effects (publish event, send email, write blob).  The service layer is the orchestrator.

You want a clean boundary between presentation (controllers) and domain.

Multiple delivery channels (web, CLI, worker) call the same use case.

# When NOT to use
Services become a dumping ground of unrelated methods on a god-class — split by use case.

The service has zero orchestration (just delegates to one repo call) — call the repo directly.

# Structure
AppService classes named by use case domain (DroneCommandAppService, DeviceIngestionAppService).  Methods take DTOs, return DTOs.  Inside: load aggregate → mutate → save → publish event.

# Example
```csharp
public class DroneCommandAppService {
    public async Task<DroneCommand> IssueAsync(IssueRequest req, CancellationToken ct) {
        var drone = await _drones.GetAsync(req.DroneId, ct);
        var cmd = drone.Issue(req.Verb, req.Payload, _clock.Now);
        await _drones.SaveChangesAsync(ct);
        await _broadcaster.BroadcastAsync(cmd, ct);
        return cmd;
    }
}
```

# Relationships
Foundation of clean-architecture Application layer.  Pairs with repository-pattern.  Distinct from Domain Service (DDD) which has domain logic that doesn't fit an entity.
