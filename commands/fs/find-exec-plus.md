---
slug: find-exec-plus
name: find . -name <pattern> -exec <cmd> {} +
family: fs
platform: cross-platform
equivalents: fd <pattern> -x <cmd> (rust replacement, much faster)
references: man find
---

# Command
```sh
find . -type f -name '<pattern>' -exec <cmd> {} +
```

# When to use
Run a command across many matched files efficiently. Pipeline alternative is `xargs`.

# When NOT to use
Simple grep — use `grep -rE` directly.
Very fast matching — use `fd` (rust-based, respects .gitignore, much faster).
Files you want to delete — use `-delete` instead of `-exec rm` (faster and safer).

# Gotchas
- `{} +` (with plus) batches matches into ONE `<cmd>` invocation per batch — much faster than `{} \;` which forks a process per file.
- `\;` forks a process per file. Use only when the command can take exactly one arg.
- `-name` is case-sensitive; `-iname` for case-insensitive.
- Watch quoting: `find . -name '*.txt'` (quoted) vs `find . -name *.txt` (shell expands glob first — often wrong).
- For binary-vs-text decisions, pipe to grep -I.

# Flags
- `-type f|d|l`: file / dir / symlink
- `-name <glob>` / `-iname` (case-insens)
- `-exec <cmd> {} +`: batched exec
- `-exec <cmd> {} \;`: one exec per file
- `-delete`: built-in delete (no process fork)
- `-mtime -7`: modified in last 7 days (`-mmin -10` for minutes)
- `-size +100M`: files larger than 100 MB
- `-not <test>`: invert

# Examples
- Touch all .py: `find . -type f -name '*.py' -exec touch {} +`
- Delete .pyc: `find . -name '*.pyc' -delete`
- Big files: `find . -type f -size +100M`
- Recently changed: `find . -type f -mtime -1`
- Grep across matched files: `find . -name '*.ts' -exec grep -l 'TODO' {} +`
