---
slug: eventually-consistent-replication
name: Eventually Consistent Replication
category: offline
intent: Accept that replicas may diverge transiently; guarantee convergence given pause in writes
references: Werner Vogels 'Eventually Consistent'; DDIA
---

# When to use
Multi-region / multi-device systems where strong consistency is too expensive or impossible.

Read-heavy workloads where reading stale-by-seconds is fine.

Offline + sync architectures where partitions are normal, not exceptional.

# When NOT to use
Operations require strong consistency (bank balances, inventory counts under contention).

Users would be confused or harmed by seeing stale state.

# Structure
Writes accepted at any replica.  Replicas exchange changes asynchronously.  Conflicts resolved by CRDT / LWW / vector clocks.  System provides 'monotonic reads' and 'read-your-writes' guarantees where possible.

# Example
swarm state in mz-pid-tuner; the Acme fleet view eventually consistent with edge devices.

# Relationships
Pairs with crdt.  Pairs with local-first-architecture.  Foundation of distributed-systems.
