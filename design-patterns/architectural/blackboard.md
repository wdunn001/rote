---
slug: blackboard
name: Blackboard
category: architectural
intent: Let multiple independent specialist components incrementally contribute partial solutions to a shared, evolving artifact, coordinated by a controller, when no single component and no fixed sequence of steps can solve the problem alone.
references: Buschmann et al., "Pattern-Oriented Software Architecture" (POSA, 1996), Blackboard. Origin: HEARSAY-II speech recognition.
---

# When to use

The problem has no deterministic algorithm but is solvable by combining diverse expert contributions.

Each specialist can watch the shared state and act only when it has something to add.

The solution emerges by accumulation and refinement, not by running a fixed pipeline.

# When NOT to use

A clear deterministic algorithm exists; just write it.

Contributions are independent one-shot responses that do not build on each other; use [[scatter-gather]].

Heavy shared mutable state would create unmanageable contention or ordering bugs.

# Structure

Three parts. A Blackboard holds the shared evolving solution state. Knowledge Sources are independent specialists that read the blackboard and write contributions when applicable. A Control component decides which source acts next based on the current state. Specialists touch only the blackboard, never each other.

# Example

Speech recognition combining acoustic, lexical, and syntactic specialists against one shared hypothesis. In [[stenographic-mediator]], each discipline (legal writes the compliance approach, infra the topology, security the threat model) contributes its own real work to the shared story, assembled without a meeting.

# Relationships

The "each discipline contributes its own invention" core of [[stenographic-mediator]]. Shares central-shared-state with [[mediator]] and [[canonical-data-model]]. The modern multi-agent echo is [[multi-agent-orchestration]]. Where contributions are parallel and independent rather than cumulative, use [[scatter-gather]].
