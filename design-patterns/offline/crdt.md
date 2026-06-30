---
slug: crdt
name: CRDT (Conflict-free Replicated Data Type)
category: offline
intent: Data types where concurrent edits merge deterministically without coordination
references: Shapiro et al. 'Conflict-free Replicated Data Types'; Automerge; Yjs
---

# When to use
Multi-device editing of the same data with possibly-disconnected periods.

Distributed counters / sets that need to converge after partition heals (Acme swarm state).

You want NO server-side merge logic — the math guarantees convergence regardless of message order.

# When NOT to use
Operations are intrinsically serial (a bank ledger — order matters for correctness).

The data has invariants CRDTs can't express (a unique constraint across the dataset).

You haven't picked the right CRDT — picking 'just an LWW register' for something complex causes silent data loss.

# Structure
Operations are commutative + associative + idempotent (or use vector clocks).  Common CRDTs: G-Counter, PN-Counter, LWW-Register, OR-Set, RGA (sequence).  Sync exchanges deltas or full state.

# Example
```cpp
// Swarm peer-state in mz-pid-tuner uses LWW-Register per peer:
struct PeerEntry {
    PeerIdentity id;
    uint64_t lamport_stamp;
    PeerState state;
};
// Merge: pick higher lamport_stamp; ties broken by peer id.
```

# Relationships
Foundation of local-first-architecture sync engines.  Pairs with vector-clocks-lww.  Alternative to operational-transform.  Used in mz-pid-tuner swarm_state.
