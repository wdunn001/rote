---
slug: git-stash
title: git stash silently loses work
hit_count: 5
token_cost: critical — entire feature implementations have vanished into stashes that were never recovered
---

# Symptom

Claude (or the user) runs `git stash` to clear a working tree before some operation, the operation succeeds, and `git stash pop` is either never run, fails on conflict and gets abandoned, or the stash is on a sibling submodule the user forgot about. Work disappears.

# Root cause

`git stash` is intentionally ephemeral and easy to miss. There's no UI for "you have stashes". Across submodules, each submodule has its own stash list. WSL + Windows-mounted repos compound this — stashes on one mount can be invisible from another shell.

# Remedy

**Banned.** Use a WIP commit on a branch instead:

```bash
git switch -c wip/working-tree-snapshot-$(date +%Y%m%d-%H%M%S)
git add -A
git commit -m "WIP: snapshot before <operation>"
git switch -
# now original branch is clean; the WIP is preserved as a real commit
```

If you find an existing stash, **promote it to a branch immediately**:

```bash
git stash branch wip/recovered-stash-N stash@{N}
git commit -m "WIP: promoted from stash"
```

# Detection

If you see `git stash` in a Claude tool call, that's the smell. Always WIP-commit on a branch.

For audit: `git stash list` per repo; `git submodule foreach --recursive git stash list` for submodule trees.

# See also

- [[feedback-never-use-git-stash]]
- [[project-marathon-lost-work-recovery]]
