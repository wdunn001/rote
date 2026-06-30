---
slug: goal-format-outcome
name: Goal Format — Outcome / Constraints / Done-When
category: efficiency
tags: goal-format, framing, requirements, scoping
---

# Prompt

Restate ${TASK} in this structure before doing any work, then proceed:

- **Outcome:** the observable end state in one sentence (what is true when this is done).
- **Why:** the underlying need this serves (so trade-offs can be judged).
- **Constraints:** hard limits — must / must-not (stack, compat, perf, security, scope boundaries).
- **Inputs on hand:** what's already provided vs. what you'll have to find or assume.
- **Done-when:** a concrete, checkable acceptance test (the exact command/observation that proves success).
- **Out of scope:** what you will deliberately NOT do.

If any of these is ambiguous and the answer changes your approach, ask one tight clarifying question. Otherwise pick the sensible default, state it, and continue.

# When to use

The start of any non-trivial task — converts a vague ask into a checkable contract and surfaces hidden assumptions cheaply.
