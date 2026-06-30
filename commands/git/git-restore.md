---
slug: git-restore
name: git restore (modern unstage + revert)
family: git
platform: cross-platform
equivalents: git reset HEAD <file>; git checkout -- <file>  (the deprecated forms)
references: https://git-scm.com/docs/git-restore
---

# Command
```sh
git restore --staged <file>   # unstage
git restore <file>            # discard working-tree changes
```

# When to use
Unstage a file you accidentally `git add`'d. Or discard uncommitted changes in working dir.

# When NOT to use
Already-pushed changes — use `git revert <sha>` (creates an inverse commit).
Stashed changes — `git stash` and friends (which we DON'T use; see `git-stash` anti-pattern — use WIP commits instead).

# Gotchas
- `git restore <file>` IS DESTRUCTIVE — your uncommitted changes in that file are gone. No reflog, no recovery.
- `git restore --staged <file>` only unstages; the working dir copy is untouched.
- Without `--staged` or `--worktree`, defaults to `--worktree` (i.e. destroys uncommitted changes).
- For 'undo last commit but keep changes': `git reset --soft HEAD~1`. Not `git restore`.

# Flags
- `--staged`: unstage
- `--worktree`: discard working-tree changes (default)
- `--source=<commit>`: restore from a specific commit instead of HEAD
- `-p` / `--patch`: interactive hunk selection

# Examples
- Unstage one file: `git restore --staged src/index.ts`
- Discard local changes: `git restore src/index.ts` (DESTRUCTIVE)
- Restore old version: `git restore --source=HEAD~3 src/index.ts`
