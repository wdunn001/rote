---
slug: du-sh-vs-ncdu
name: du -sh / ncdu (disk-usage analysis)
family: fs
platform: cross-platform
equivalents: WinDirStat (Windows); GrandPerspective (macOS)
references: man du; https://dev.yorhel.nl/ncdu
---

# Command
```sh
du -sh ./*          # quick per-toplevel
ncdu -x /         # interactive TUI
```

# When to use
Find what's eating disk space. `du -sh` for a quick scan; `ncdu` for interactive drill-down.

# When NOT to use
Watching disk in real-time — `iotop`, `iostat`. 
Docker disk — `docker system df`.

# Gotchas
- `du -sh ./*` skips dotfiles. Use `du -sh ./* ./.*` to include them, OR `du -sh .[!.]* *` to include dotfiles but not `.` and `..`.
- `du` counts BLOCK USAGE, not byte size. On filesystems with large block sizes, small files appear bigger.
- `du -h` is human-readable; for sorting use `du -sb` (bytes) and `sort -n`.
- `ncdu -x` stays on one filesystem (won't cross mount points — important on root).
- For very large filesystems, `ncdu` can be slow to scan; consider `--exclude` patterns.

# Flags
du:
- `-s`: summary (just the total)
- `-h`: human-readable (K/M/G)
- `-x`: one filesystem only
- `--max-depth=N`

ncdu:
- `-x`: one filesystem
- `--exclude <pattern>`: skip
- `-o <file>`: dump scan to file (offline analysis)

# Examples
- Per-toplevel: `du -sh ./* | sort -h`
- Including dotfiles: `du -sh .[!.]* * | sort -h`
- Interactive drill: `ncdu -x /`
- Save then view: `ncdu -o /tmp/scan.json /var; ncdu -f /tmp/scan.json`
