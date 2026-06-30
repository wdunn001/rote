---
slug: pr-description
name: PR Description from a Diff
category: delivery
tags: pr, review, summary, delivery
---

# Prompt

Write a pull-request description for the changes on this branch (diff against ${BASE_BRANCH}).

Structure:
- **What & why:** the change in 1–2 sentences and the problem it solves.
- **Approach:** the key decisions a reviewer needs to understand the diff (not a file-by-file walk).
- **Risk & blast radius:** what could break, what's backward-incompatible, what's feature-flagged.
- **Testing:** how it was verified (commands, cases covered) and what was NOT covered.
- **Reviewer guide:** where to focus, and anything you're unsure about.

Base it on the real diff. Keep it skimmable — a reviewer should grasp the change in under a minute. Flag anything you'd want a second opinion on.

# When to use

Opening a PR you want reviewed quickly and correctly — give reviewers the map, the risks, and the verification.
