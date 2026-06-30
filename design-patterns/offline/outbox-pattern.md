---
slug: outbox-pattern
name: Outbox Pattern
category: offline
intent: Write business state + outbound messages in one local transaction; a separate process drains messages to the wire
references: Microservices Patterns by Chris Richardson
---

# When to use
Need to atomically update a DB AND publish an event/message.  The 'and' is the hard part (two-phase commit is fragile; dual writes are broken).

You want at-least-once delivery without losing messages on crash.

Offline-first systems: messages queue locally and flush when connectivity returns.

# When NOT to use
Fire-and-forget that doesn't matter if lost (analytics ping).

You can use a transactional log feature directly (PostgreSQL logical replication, change-data-capture) — that's the outbox built-in.

# Structure
Application writes business state + an Outbox row in the same DB transaction.  A separate poller / CDC subscriber reads Outbox, publishes to the wire, marks rows as sent.  At-least-once: subscribers must be idempotent.

# Example
```sql
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE id = $1;
INSERT INTO outbox (kind, payload) VALUES ('AccountDebited', $2);
COMMIT;
```
A background worker selects unsent outbox rows, publishes, marks sent.

# Relationships
Foundation of reliable event publication.  Pairs with idempotency-token (downstream dedup).  Pairs with eventually-consistent-replication.  Used in Acme CoT bridge between API and TAK fan-out.
