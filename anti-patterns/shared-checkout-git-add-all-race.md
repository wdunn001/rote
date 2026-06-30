---
slug: shared-checkout-git-add-all-race
title: Concurrent git add -A on a shared deploy checkout swept my uncommitted work into another session's commit
hit_count: 1
token_cost: medium — work attribution lost into another commit; near-miss on losing the last file
---

# Symptom

Worked across many files in `~/dev/example-app` (a shared deploy checkout), batching commits for the end. By the time I went to commit, `git status` showed most of my files as already clean/committed — a parallel workstream's `git add -A && git commit` had absorbed my uncommitted edits into ITS commits. Only the single most-recently-edited file was still mine to commit.

# Root cause

The working tree is shared by multiple concurrent agents/sessions and a deploy process. Any `git add -A` by another actor stages and commits whatever is currently dirty — including your in-progress, unattributed work.

# Remedy

- On shared/deploy checkouts, commit each green slice **immediately** with **explicit pathspecs**: `git add path/a path/b && git commit`. Never `git add -A` / `git add .`.
- Don't hold uncommitted work across long background runs on a shared tree.
- If you must isolate, use a `git worktree` in `/tmp` (see [[git-stash]] neighbors / the hotfix-in-worktree rule) rather than editing the deploy checkout directly.
- When you find your work already committed by someone else, verify content is intact in HEAD (`git show HEAD:path`) before assuming loss.
