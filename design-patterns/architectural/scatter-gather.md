---
slug: scatter-gather
name: Scatter-Gather
category: architectural
intent: Send one request to multiple recipients in parallel and aggregate their responses into a single result, so total latency is the slowest responder rather than the sum, and recipients stay independent.
references: Hohpe & Woolf, "Enterprise Integration Patterns" (2003), Scatter-Gather (Recipient List or Publish-Subscribe + Aggregator).
---

# When to use

A task needs input, quotes, or approval from several independent parties.

The parties can work concurrently and do not depend on each other's output.

You care about wall-clock latency and want it bounded by the slowest responder, not the chain.

# When NOT to use

Steps depend on each other and must run in sequence.

Responders contend on shared mutable state, so parallelism creates conflicts.

You need all-or-nothing transactional semantics across the responses; see [[saga]].

# Structure

A distributor fans the request out via a Recipient List (known addressees) or Publish-Subscribe (open set). An Aggregator collects responses, applies a completeness condition (all, quorum, or first-by-timeout), and merges them into one result. The aggregation strategy and the timeout are the load-bearing choices.

# Example

A quote request broadcast to several suppliers, returning the best price within a deadline. In [[stenographic-mediator]], a single work item routed to legal, infra, and security at once for parallel sign-off instead of crawling through sequential meetings.

# Relationships

The parallelism behind [[stenographic-mediator]]. Its aggregation cousin is [[blackboard]] (accumulate contributions over time). Should be bounded by [[timeout-and-deadline]] and isolated with [[bulkhead]]. Contrast sequential [[chain-of-responsibility]]. Where responses must commit atomically, escalate to [[saga]].
