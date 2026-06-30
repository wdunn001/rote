---
slug: ensurecreated-no-tables-on-existing-db
title: New EF entity "done" but its table never exists on the existing prod DB (EnsureCreated is a no-op there)
hit_count: 1
token_cost: medium — feature ships as code, works on fresh dev DB, silently has no table/data on prod; invisible until you query prod (often classifier-blocked)
---

# Symptom

You add a new EF entity + DbSet, it works locally, you commit and deploy. On prod the feature has no data and the endpoint returns nothing or errors with "relation does not exist." The code is deployed; the table is not.

# Root cause

EF Core `Database.EnsureCreatedAsync()` only builds schema on a **fresh/empty** database. On an existing DB (prod) it is a no-op — it does NOT add new tables to an already-created schema. New tables reach an existing prod DB only via an explicit brownfield DDL step. On a fresh dev DB EnsureCreated makes everything, so it looks done locally; the gap is invisible until you inspect prod.

# Remedy (deterministic)

Ship a brownfield `IHostedService` (e.g. `Ensure<Thing>SchemaHostedService`) that runs the DDL at startup, registered in `Program.cs`. Generate the DDL FROM the EF model so it can't drift from the entity (see design-pattern `ddl-from-orm-model`):

```csharp
string script = db.Database.GenerateCreateScript();   // full model DDL
// execute only the CREATE TABLE/INDEX statements for YOUR target tables,
// idempotent: skip if to_regclass(table) is not null; catch 42P07 duplicate_table.
```

Register it BEFORE any seeder that depends on the table. Treat the brownfield service as part of the SAME slice as the entity — not a follow-up.

# Detection

A new entity is NOT done until its table exists on the existing prod DB. Checklist before claiming done:
- Is there an `Ensure*SchemaHostedService` for the new table(s), registered in `Program.cs`?
- Did you confirm on the deployed app (create a row, see it) — not just "builds locally"?

Relates to the rule: "done" = shipped + viewable, not committed.
