---
slug: sed-in-place
name: sed -i 's/from/to/g' (in-place file edit)
family: text
platform: cross-platform
equivalents: perl -pi -e 's/from/to/g' (works identically on mac+linux); GNU sed (linux); BSD sed (macos)
references: man sed
---

# Command
```sh
sed -i 's/<pattern>/<replacement>/g' <file>
```

# When to use
Quick in-place text substitution in one file. For multi-file, prefer the library's `find-replace-tree.sh` (handles backups, gitignore, etc.).

# When NOT to use
Codebase-wide replace — use `scripts/find-replace-tree.sh` (backup + glob filter + dry-run).
Structural edits — use a real parser (Tree-sitter, AST tools).
Irreversible edits without backup — at minimum add `.bak` suffix: `sed -i.bak 's/.../.../'`.

# Gotchas
- macOS (BSD sed) REQUIRES an extension after `-i`: `sed -i '' 's/.../.../' file`. GNU sed (linux): `sed -i 's/.../.../' file`. Use `sed -i.bak 's/.../.../'` for portable code (works on both, produces .bak files you can delete).
- The delimiter is by convention `/` but ANY char works. Use a different delimiter when your patterns contain slashes: `sed 's|/foo|/bar|g'`.
- `&` in the replacement is the WHOLE match. `\1`, `\2`, etc. are capture groups (with `-E` or escaped `\(...\)`).
- For multi-line / structural edits, sed is the wrong tool. Use `awk` or a real script.

# Flags
- `-i [<ext>]`: in-place; with ext (e.g. `.bak`) for a backup; without, modify directly
- `-E`: extended regex (so `+`, `?`, `()` work without `\`)
- `-n`: silent (only print what you tell it to with `p`)
- `-e <script>`: explicit script (allows multiple)
- `-f <scriptfile>`: read commands from file

# Examples
- Replace one file: `sed -i 's/old_string/new_string/g' config.yaml`
- Portable backup-first: `sed -i.bak 's/foo/bar/g' file.txt`
- Multi-line delete: `sed -i '/^# DELETE_ME/,/^# END_DELETE/d' file.txt`
- With non-slash delimiter: `sed -i 's|/old/path|/new/path|g' file.txt`
