---
slug: ps-aux-grep
name: ps aux | grep <pattern>
family: monitoring
platform: cross-platform
equivalents: pgrep -af <pattern> (cleaner output); top / htop (interactive)
references: man ps; man pgrep
---

# Command
```sh
ps aux | grep -v grep | grep <pattern>
```

# When to use
Quick check: is <process> running, and what's its PID / command line?

# When NOT to use
Production monitoring (use proper observability). Scripted PID lookups — use `pgrep` or `pidof` instead (no need to filter out grep itself).

# Gotchas
- `ps aux | grep foo` ALWAYS matches the grep itself unless you filter (`grep -v grep`). The classic gotcha.
- `pgrep -af <pattern>` is cleaner; `-a` shows full command, `-f` matches against full command line (not just basename).
- Pre-systemd / pre-cgroup, this was the only way to identify processes. Now: `systemctl status` for services, `docker ps` for containers.

# Flags
ps:
- `a`: show processes of other users
- `u`: detailed user-oriented output
- `x`: include processes not attached to a terminal
- `-ef`: BSD-style is `aux`; SysV-style is `-ef`. Both work on Linux.

pgrep:
- `-a`: show command line
- `-f`: match against full command line
- `-u <user>`: scope to a user

# Examples
- Is nginx running: `pgrep -af nginx`
- All python processes: `pgrep -af python`
- Sort by CPU: `ps aux --sort=-%cpu | head`
- By memory: `ps aux --sort=-%mem | head`
