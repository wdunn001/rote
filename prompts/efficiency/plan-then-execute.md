---
slug: plan-then-execute
name: Plan-Then-Execute (cheap plan before expensive work)
category: efficiency
tags: planning, efficiency, dry-run, approval
---

# Prompt

Before changing anything for ${TASK}, produce a short plan I can approve:

1. The 3–7 steps you'll take, in order.
2. The files/systems each step touches.
3. The riskiest step and how you'll de-risk it (dry-run, backup, smallest reversible change first).
4. What you'll verify at the end and how.

Keep the plan scannable — no prose padding. Then STOP and wait for my go-ahead. After approval, execute the plan, reporting only deviations from it (not a replay of every step). If reality diverges from the plan mid-execution, pause and tell me what changed before improvising.

# When to use

Tasks with real blast radius (migrations, deploys, deletes, refactors) where a 30-second plan prevents an expensive wrong turn.
