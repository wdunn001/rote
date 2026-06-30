---
slug: postgresql
name: PostgreSQL
category: database
implements_patterns: repository-pattern, outbox-pattern, event-sourcing
tags: self-hosted, offline-capable, open-source, sql, jsonb
references: https://www.postgresql.org/
---

# When to use
General-purpose SQL DB for transactional apps.

You want JSONB columns when domain models have flexible schema (Acme uses jsonb extensively).

LISTEN/NOTIFY for in-DB pub/sub.

Extensions: pgvector for embeddings, PostGIS for geo, TimescaleDB for time-series.

Acme's primary DB.

# When NOT to use
You need horizontal scale across many writers — Postgres scales to a point; if you need cross-region active-active, look at CockroachDB / YugabyteDB / Spanner.

Pure document store with no relational needs — MongoDB / DynamoDB are simpler for some shapes.

Edge / device storage — SQLite is the answer.

# Limitations
- Vertical scale only out of the box (logical replication helps reads; writes scale via partitioning + sharding effort).
- Schema migrations on huge tables need careful planning.
- Connection pooling needs a pooler (PgBouncer) at scale.

# Cost
Free open-source.  Cloud-managed: AWS RDS / Azure Postgres / Supabase / Neon — pay for compute + storage + IO.

# Alternatives
MySQL/MariaDB (similar shape).  SQL Server (.NET-native, commercial).  SQLite (embedded).  CockroachDB (horizontally scalable Postgres-compatible).
