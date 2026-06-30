---
slug: conventional-commit
name: Conventional Commit Message
category: delivery
tags: git, commit, conventional-commits
---

# Prompt

Write a commit message for the staged changes.

1. Read the actual diff — base the message on what changed, not what I said I'd do.
2. Use Conventional Commits: `type(scope): subject` where type is feat/fix/refactor/perf/docs/test/chore/build/ci. Imperative mood, ≤72 chars, no trailing period.
3. Body (only if it adds value): WHY the change was made and any non-obvious consequence — not a restatement of the diff.
4. Note breaking changes with a `BREAKING CHANGE:` footer.
5. One logical change per commit — if the diff is really two changes, tell me and propose splitting it.

Output just the message. Match the repo's existing commit style if it diverges from the above.

# When to use

Turning a staged diff into a clean, honest commit message that reflects the real change.
