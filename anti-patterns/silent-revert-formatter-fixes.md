---
slug: silent-revert-formatter-fixes
title: Reverting auto-formatter / lint fixes thinking they're noise
hit_count: 2
token_cost: high — re-introduces violations of project rules, wastes the contributor's work, reviewer has to flag it
---

# Symptom

A previous commit landed a sweep that fixed N instances of a rule violation across a codebase (e.g. `var foo` → `Foo foo`, or branding string `mz-` → `acme-`). Later, you (Claude or human) see a big diff full of these mechanical changes and assume they're formatter noise, then revert them while making an unrelated edit.

# Root cause

Sweep diffs LOOK like noise: hundreds of nearly-identical line changes with no business-logic content. The mechanical nature hides the fact that each change is a deliberate landing of a project rule.

# Remedy

Before reverting any "looks like formatter noise" diff:

1. `git log --oneline -- <file>` — check the commit message of the most recent author of the touched lines.
2. If the commit says "rule: ..." / "convention: ..." / "branding: ..." — **do not revert**. The "noise" IS the rule landing.
3. If you genuinely need to undo it, only revert in scope, and write a commit message that names which rule you're rolling back and why.

# Detection

Any time you see a `git revert` or `git checkout -- <file>` undoing dozens of identical mechanical changes — pause. Read the commit being reverted. If it's a rule-landing commit, do not revert.

# See also

- [[implicit-var-in-csharp]]
- [[feedback-no-implicit-var]]
