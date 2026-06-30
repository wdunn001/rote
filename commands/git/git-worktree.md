---
slug: git-worktree
name: git worktree add (parallel checkouts)
family: git
platform: cross-platform
equivalents: 
references: https://git-scm.com/docs/git-worktree
---

# Command
```sh
git worktree add ../<dir> <branch>
```

# When to use
Work on two branches simultaneously without `git stash` or duplicate clones. Each worktree has its own working dir; they share the .git directory.

# When NOT to use
Working on the same branch in two worktrees (git refuses by default; for good reason).
Long-term — worktrees can be forgotten and leak state. Use `git worktree list` + `git worktree remove` regularly.

# Gotchas
- Worktrees share refs but NOT the working directory. Changes in one don't affect another.
- `git worktree remove` cleans up; manual `rm -rf` leaves the .git/worktrees/<name> directory dangling (use `git worktree prune` to clean).
- When the worktree branch is later merged + deleted, the worktree dir doesn't auto-clean. Remove it.
- Some Acme sessions create worktrees during agent fan-out (e.g. C3 work) — list them periodically.

# Flags
- `add <path> <branch>`: create
- `add -b <new-branch> <path>`: create a new branch in this worktree
- `list`: show all worktrees
- `remove <path>`: clean up
- `prune`: remove records of vanished worktrees
- `lock`: prevent removal (for long-running offline worktrees)

# Examples
- Bug-fix on a separate dir: `git worktree add ../myapp-hotfix hotfix/critical-bug`
- Look at the topology: `git worktree list`
- Clean up: `git worktree remove ../myapp-hotfix`
