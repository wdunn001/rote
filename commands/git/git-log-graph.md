---
slug: git-log-graph
name: git log --oneline --graph --all
family: git
platform: cross-platform
equivalents: tig (TUI); gitk (Tk GUI)
references: https://git-scm.com/docs/git-log
---

# Command
```sh
git log --oneline --graph --all --decorate
```

# When to use
Visualize branch structure + recent commits across all refs in one screen.

# When NOT to use
Repo with 10k+ commits and 100+ branches — output gets unreadable. Filter by --since / --author / --grep.

# Gotchas
- `--all` shows ALL refs including stashes and remote-tracking branches. Drop it for current branch only.
- Alias this. Most devs set `git lg` to this exact command in `~/.gitconfig`.
- The graph shows the topology truthfully; what you THINK happened may not be what did.

# Flags
- `--oneline`: one line per commit (SHA + message)
- `--graph`: ASCII branch topology
- `--all`: every ref
- `--decorate`: show ref names next to SHAs
- `--since=2w`: limit to last 2 weeks
- `--author=<pattern>`: filter by author
- `-N` (e.g. `-30`): show only the N most recent commits

# Examples
- Set as alias: `git config --global alias.lg 'log --oneline --graph --all --decorate'` then `git lg`
- Last 50 commits: `git log --oneline --graph --all -50`
- This branch only: `git log --oneline --graph -30`
