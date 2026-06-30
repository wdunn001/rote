---
slug: canonical-data-model
name: Canonical Data Model
category: architectural
intent: Define one shared, vendor-neutral data model that every system translates to and from, so N systems need N translators instead of N x N pairwise mappings, and a system can be added or replaced without touching the others.
references: Hohpe & Woolf, "Enterprise Integration Patterns" (2003), Canonical Data Model + Message Translator. Generalizes to any vocabulary-translation problem, not just messaging.
---

# When to use

Many systems exchange data in differing formats and the point-to-point translators are multiplying toward N x N.

You want to add, replace, or upgrade one system without re-touching every other integration.

A stable shared meaning exists that all parties can map onto.

# When NOT to use

Only two systems integrate; a single direct translator is simpler.

The shared model collapses to a lowest-common-denominator that loses each system's meaning.

Schemas churn so fast that a central model becomes a coordination bottleneck instead of a decoupler.

# Structure

A central, versioned canonical model is owned independently of any endpoint. Each endpoint has its own Message Translator (an [[adapter]]) converting between its native format and the canonical one. No endpoint maps directly to another.

# Example

An order canonical model that ERP, CRM, and shipping each map to and from. In the Codec wire-format work, a token-ID map translates vocabulary V_A to V_B in-process, with the human-readable form materialized only when a human is present, the same "one shared model, translate at the edges" idea.

# Relationships

The "shared vocabulary the mediator holds" core of [[stenographic-mediator]]. Enforced at a domain boundary by the [[anti-corruption-layer]]. Implemented per endpoint with [[adapter]]. Shares the central-shared-state idea with [[blackboard]] and [[mediator]].
