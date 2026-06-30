---
slug: adversarial-bug-hunt
name: Adversarial Bug Hunt
category: review-debug
tags: review, bugs, adversarial, verification
---

# Prompt

Review ${TARGET} adversarially — assume it's wrong and try to prove it.

Hunt specifically for: off-by-one and boundary errors, null/empty/unset cases, error paths that swallow or mislabel failures, race conditions and shared-state mutation, resource leaks, incorrect assumptions about input shape, and security issues (injection, authz gaps, secret handling).

For each finding:
- Quote the exact code (file:line).
- State the concrete trigger — the input or sequence that breaks it.
- Rate severity (critical / high / medium / low) and confidence.
- Give the minimal fix.

Then VERIFY each finding before reporting it: trace the path again and try to refute your own claim. Drop anything you can't substantiate. Report confirmed issues only, hardest-hitting first. If you find nothing real, say so plainly rather than padding with style nits.

# When to use

Pre-merge review or "why is this flaky" investigations where you want real defects surfaced and verified, not a lint pass.
