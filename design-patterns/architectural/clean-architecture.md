---
slug: clean-architecture
name: Clean Architecture
category: architectural
intent: Organize code so business rules don't depend on infrastructure, UI, or frameworks; outer layers point inward
references: Uncle Bob Martin; Acme uses this — see CLAUDE.md 'Architecture boundaries'
---

# When to use
Long-lived business apps where infrastructure (DBs, queues, providers) will change but business rules persist: SaaS platforms, financial systems, regulated industries.

Multiple delivery channels (web + CLI + worker + mobile) need the same business rules.

You want testability without spinning up infra (Application tests use fake adapters).

# When NOT to use
CRUD over a single DB with no business logic — a clean architecture skeleton is overhead.

Prototype / scratch code — focus on shipping; clean architecture if it survives.

# Structure
Concentric layers, dependencies point inward:
- Domain (innermost): entities, value objects, repository INTERFACES (not implementations)
- Application: use cases, ports for infra (IEmailSender, IClock)
- Infrastructure: adapter IMPLEMENTATIONS (EF Core repos, Graph email sender)
- Api / Presentation: outermost; composition root, controllers
Domain knows nothing.  Application knows Domain.  Infrastructure knows Application + Domain.  Api knows all (it wires them).

# Example
```
src/Acme.Domain/      ← entities, repository interfaces, value objects
src/Acme.Application/ ← use cases, ports, app services
src/Acme.Infrastructure/ ← EF Core, MS Graph, Service Bus adapters
src/Acme.Api/         ← controllers, composition root
```

# Relationships
Pairs with hexagonal-ports-adapters (different ways to draw the same boundary).  Pairs with repository-pattern (Domain owns the interface, Infrastructure provides it).  See also domain-driven-aggregate.
