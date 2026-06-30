---
slug: git-reflog-recovery
name: git reflog (recover from mistakes)
family: git
platform: cross-platform
equivalents: jj op log (jujutsu)
references: https://git-scm.com/docs/git-reflog
---

# Command
```sh
git reflog
```

# When to use
You did something destructive (hard reset, force-checkout, bad rebase, accidentally deleted a branch) and want to recover.

# When NOT to use
The repo has been garbage-collected (rare; default GC keeps reflog 30-90 days). For long-term recovery, you need backups.
You just want to see commits — use `git log` instead.

# Gotchas
- Reflog tracks HEAD movements LOCALLY only. Pushes / pulls record entries; remote operations on OTHER machines don't.
- After ~30 days (gc.reflogExpire default 90), reflog entries can be GC'd.
- Each ref has its own reflog: `git reflog show <branchname>`.
- `HEAD@{N}` references the Nth-most-recent HEAD position.

# Flags
- `show <ref>`: see the reflog for a specific ref (default HEAD)
- `--date=iso`: show timestamps in ISO format (easier to scan)
- `expire`: prune old entries (rarely needed)
- `delete <ref>@{N}`: remove a single entry

# Examples
- See your recent HEAD movements: `git reflog`
- Recover a lost commit: `git reflog`, find the SHA, then `git cherry-pick <sha>` or `git branch recover-<topic> <sha>`
- Restore after bad reset: `git reset --hard HEAD@{1}` (go back ONE HEAD movement)
