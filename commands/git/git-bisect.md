---
slug: git-bisect
name: git bisect (find the commit that broke things)
family: git
platform: cross-platform
equivalents: 
references: https://git-scm.com/docs/git-bisect
---

# Command
```sh
git bisect start <bad-commit> <good-commit>
# (test current commit, then) git bisect good   OR   git bisect bad
# ... repeat ...
git bisect reset
```

# When to use
A regression appeared and you don't know which commit caused it. Binary search through history with O(log N) test runs.

# When NOT to use
The regression is intermittent (bisect needs a reliable test). The commit space has merge commits with broken trees in between (bisect handles this but the noise can confuse).

# Gotchas
- ALWAYS `git bisect reset` when done — otherwise HEAD is stuck mid-bisect.
- Bisect tries the midpoint, not the average; on a non-linear history with merges this can land on a 'merge commit that doesn't compile' even though no actual code introduced the bug.
- Automate the test: `git bisect run <script>` exits 0 for good, non-zero for bad. The script runs your test on each candidate.

# Flags
- `start <bad> <good>`: kick off
- `good` / `bad`: classify the current candidate
- `skip`: this candidate can't be tested (don't classify)
- `run <command>`: automate — script's exit code classifies
- `reset`: stop and return to HEAD

# Examples
- Manual: `git bisect start HEAD HEAD~50`, then for each step test the app and run `git bisect good` or `git bisect bad`.
- Automated: `git bisect run npm test` — bisect runs `npm test` on each candidate.
