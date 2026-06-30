---
slug: grep-recursive
name: grep -rE / rg (recursive grep)
family: text
platform: cross-platform
equivalents: ripgrep (`rg`) — much faster + respects .gitignore by default; ack
references: man grep; https://github.com/BurntSushi/ripgrep
---

# Command
```sh
grep -rEn '<regex>' <path>      # POSIX, in stdlib
rg '<regex>' <path>             # ripgrep, faster + smarter
```

# When to use
Find a pattern across a tree. For dev work, `rg` (ripgrep) is the modern choice — 10-100x faster + respects .gitignore.

# When NOT to use
A specific file — just `grep <pattern> <file>`.
Need line-level structure (replacement, multi-pattern) — use the library's `find-replace-tree.sh` for write ops.

# Gotchas
- POSIX grep without `-E` uses BASIC regex (no `+`, `?`, `()` without escaping). `-E` enables extended regex (most people's mental model).
- `-r` follows symlinks by default — can produce infinite loops in weird trees. Use `-R` to follow (POSIX) but watch out.
- `--include='*.ts'` filters by glob. `--exclude='*.bak'` skips.
- `rg` respects `.gitignore`, `.ignore`, `.rgignore` automatically. Pass `--no-ignore` to disable.
- For literal strings (not regex), use `grep -F` / `rg -F`.
- For just files (not lines): `grep -l` / `rg -l`.

# Flags
grep:
- `-r`: recursive
- `-E`: extended regex
- `-n`: line numbers
- `-i`: case-insensitive
- `-l`: only filenames
- `-c`: count per file
- `-F`: fixed (literal) string
- `--include`, `--exclude`
- `-C N`: N lines of context

rg:
- All the above plus:
- `-t <type>` / `-T <type>`: file-type filter (`rg -t py 'foo'`)
- `--hidden`: include dotfiles
- `--no-ignore`: ignore .gitignore
- `-S` / `--smart-case`: lowercase = insensitive, mixed = sensitive

# Examples
- POSIX: `grep -rEn 'TODO' src/`
- Filter type: `grep -rEn --include='*.ts' 'useState' src/`
- ripgrep modern: `rg 'TODO' src/`
- Just files: `rg -l 'export function' src/`
- Context: `rg -C 3 'Error' /var/log/`
