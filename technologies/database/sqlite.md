---
slug: sqlite
name: SQLite
category: database
implements_patterns: repository-pattern, local-first-architecture
tags: embedded, offline-capable, open-source, sql
references: https://www.sqlite.org/
---

# When to use
On-device storage (mobile, edge, IoT, drones).

Single-process server-side cache / log (the rote uses SQLite for audit + anti_patterns + design_patterns + script_run_log).

Test fixtures + ephemeral data.

Local-first apps where the device is the primary owner of the data.

# When NOT to use
Many concurrent writers (SQLite supports one writer at a time; WAL mode helps but isn't unlimited).

You need network access to the DB — SQLite is file-based.

You need replication / HA out of the box — Litestream and rqlite help but aren't seamless.

# Limitations
- Single-writer constraint.
- Schema migration on a running app needs care (PRAGMA user_version, careful ALTER).
- Some extensions (sqlite-vec) need loadable extension support — disabled in some hosts.

# Cost
Free.  Zero infra.

# Alternatives
Postgres (when you need a server).  DuckDB (analytical SQLite).  LMDB / RocksDB (key-value embedded).  Litestream (SQLite + S3 replication).
