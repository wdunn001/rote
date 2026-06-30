---
slug: root-cause-five-whys
name: Root-Cause (not symptom) Debugging
category: review-debug
tags: debugging, root-cause, evidence
---

# Prompt

Debug ${SYMPTOM} to the root cause — do not patch the symptom.

1. Reproduce it reliably first; state the exact repro and the observed-vs-expected behavior.
2. Form 2–3 hypotheses for the cause, ranked by likelihood given the evidence.
3. Test the top hypothesis with a targeted observation (log, breakpoint, bisect, minimal repro) BEFORE changing code. Let evidence, not guesses, narrow it.
4. Keep asking "but why did that happen?" until you reach a cause that, if fixed, prevents the whole class of failure — not just this instance.
5. Propose the fix at the root, plus a check that would have caught it (test/assert/guard).

Show your evidence trail. If you change code speculatively, say so and verify the change actually resolves the reproduced failure.

# When to use

A bug whose obvious "fix" would just move the symptom — you want the underlying cause and a guard against recurrence.
