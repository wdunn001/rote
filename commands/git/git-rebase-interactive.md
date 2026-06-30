---
slug: git-rebase-interactive
name: git rebase -i HEAD~N (interactive rebase)
family: git
platform: cross-platform
equivalents: jj edit (jujutsu)
references: https://git-scm.com/docs/git-rebase
---

# Command
```sh
git rebase -i HEAD~<N>
```

# When to use
Squash, reorder, edit, or drop the last N commits before pushing. Clean up a feature branch's history for a PR.

# When NOT to use
Commits already pushed to a shared branch — you'll force-push and rewrite history other people depend on. ONLY use on personal branches before pushing.
More than ~20 commits — interactive rebase becomes unwieldy. Use `git filter-repo` or `git rebase --autosquash` for systematic operations.

# Gotchas
- The editor opens with the COMMITS BUT THE ORDER IS REVERSED FROM `git log`. Top of the file = oldest commit; bottom = newest.
- `pick`, `reword`, `edit`, `squash`, `fixup`, `drop`, `exec`. Most-used: `squash` and `fixup`.
- `squash` keeps the commit message; `fixup` discards it (use when the original message was junk like 'fix typo').
- If you mess up: `git reflog` shows every HEAD change; `git reset --hard HEAD@{<N>}` restores.
- `--autosquash` + `--autostash` are quality-of-life: autosquash if your commits are tagged `fixup!` / `squash!`; autostash for uncommitted changes.

# Flags
- `-i` / `--interactive`: open editor (the whole point)
- `--autosquash`: auto-mark `fixup!` / `squash!` commits
- `--autostash`: stash working tree before, restore after
- `--continue` / `--abort` / `--skip`: control flow after a conflict
- `--onto <newbase>`: change WHAT we're rebasing onto (advanced)

# Examples
- Squash last 3 commits into one: `git rebase -i HEAD~3`, change all but the first to `squash`.
- Drop a bad commit: `git rebase -i HEAD~5`, change line to `drop`.
- Edit a commit's message 4 back: `git rebase -i HEAD~4`, change line to `reword`.
