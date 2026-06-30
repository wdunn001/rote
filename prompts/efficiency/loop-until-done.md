---
slug: loop-until-done
name: Loop Until Done (closed-loop completion)
category: efficiency
tags: looping, autonomy, completion, verification
---

# Prompt

Work on ${GOAL} in a closed loop until it is genuinely done, not until it looks done.

Each iteration:
1. State the single next concrete step and why it's next.
2. Do it.
3. VERIFY the result with an objective check (run it, test it, diff it, read the output) — not by asserting success.
4. If the check fails, diagnose the root cause before retrying; do not retry the same action unchanged.
5. Update a short running checklist of what's done / what remains.

Stop only when every item on the checklist is verified complete. If you hit a blocker you cannot resolve, stop and surface it explicitly with: what you tried, the evidence, and the specific decision you need from me. Do not silently skip, stub, or declare partial work "done."

# When to use

Multi-step tasks you want driven to true completion with self-verification each step, instead of a single optimistic pass.
