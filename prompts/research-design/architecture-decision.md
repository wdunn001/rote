---
slug: architecture-decision
name: Architecture Decision (options + ADR)
category: research-design
tags: architecture, adr, trade-offs, decision
---

# Prompt

Help me decide how to build ${CAPABILITY}, then record it as an ADR.

1. Restate the problem, the forces (constraints + quality attributes: perf, offline, cost, ops, security), and what success looks like.
2. Lay out 2–4 viable options. For each: how it works, what it's good at, where it hurts, and which forces it satisfies/violates.
3. Check the library first — is there a recorded pattern, technology, or prior stack outcome for this? Reuse the canonical shape; don't reinvent.
4. Recommend one, with the explicit reason it wins given THESE forces (not in the abstract).
5. Write the decision as a short ADR: context, options considered, decision, consequences (including what we're accepting/giving up).

Bias toward the simplest option that meets the constraints. Name what would make you reconsider.

# When to use

A design fork worth thinking through deliberately and recording, so the reasoning survives past the moment.
