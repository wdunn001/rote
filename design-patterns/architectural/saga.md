---
slug: saga
name: Saga (Process Manager)
category: architectural
intent: Coordinate a long-running, multi-step process across independent parties without a distributed transaction, by running a sequence of local steps each paired with a compensating action that undoes it if a later step fails, yielding eventual consistency with explicit rollback.
references: Garcia-Molina & Salem, "Sagas" (1987). Hohpe & Woolf Process Manager (EIP). Microservices saga, orchestration vs choreography.
---

# When to use

A workflow spans multiple services or parties and cannot be held inside one ACID transaction.

You need eventual consistency with an explicit, business-defined rollback path.

Every forward step can be compensated (refund a charge, cancel a booking, release a hold).

# When NOT to use

A single local ACID transaction already covers the work.

Steps have irreversible side effects with no meaningful compensation.

Strong immediate consistency across all parties is a hard requirement.

# Structure

Orchestrated: a central coordinator (process manager) drives each step and, on failure, invokes the compensations in reverse. Choreographed: each step emits an event the next step reacts to, with no central brain. Either way, every forward action T_i has a compensation C_i applied in reverse order when a later step fails.

# Example

Book flight, then hotel, then car; if the car step fails, compensate by cancelling the hotel and flight. In [[stenographic-mediator]], scope shifting mid-stream is handled as a saga: the parts of the work invalidated by the change are compensated and re-derived, so committed expert work is not silently lost.

# Relationships

The long-running coordination and compensation property of [[stenographic-mediator]]. Reliable steps pair with [[outbox-pattern]] and [[idempotency-token]]. It sequences and makes transactional what [[scatter-gather]] parallelizes. Contrast [[event-sourcing]] (an immutable log of facts rather than compensations).
