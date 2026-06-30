---
slug: systemctl-restart
name: systemctl restart / status / enable
family: systemd
platform: debian, ubuntu, fedora, arch
equivalents: service <name> restart (sysv-init, deprecated); launchctl (macos); sc.exe (windows)
references: man systemctl
---

# Command
```sh
systemctl status <unit>
systemctl restart <unit>
systemctl enable --now <unit>   # enable at boot AND start now
systemctl daemon-reload          # after editing a unit file
```

# When to use
Manage systemd services on a Linux host (the vast majority of modern distros).

# When NOT to use
Container-runtime processes — docker/podman manage those.
User-session services — use `systemctl --user <verb>`.

# Gotchas
- After editing a unit file at `/etc/systemd/system/<unit>.service`, you MUST `systemctl daemon-reload` before `restart`, otherwise the old definition is still loaded.
- `enable` makes it start at boot; `start` makes it run now. `enable --now` does both.
- `restart` is NOT a graceful reload — it kills + restarts. For nginx-style reload: `systemctl reload <unit>` (only if the unit defines ExecReload).
- `journalctl -u <unit> -f` is the standard way to follow a service's logs.

# Flags
- `start` / `stop` / `restart` / `reload`
- `enable` / `disable`: boot-time auto-start
- `enable --now`: enable + start in one
- `status`: current state + last log lines
- `daemon-reload`: re-read unit files after edits
- `--user`: operate on user-scope unit
- `list-units --type=service --state=running`: enumerate running services

# Examples
- Restart api: `sudo systemctl restart acme-api`
- Enable + start: `sudo systemctl enable --now acme-api`
- Inspect: `sudo systemctl status acme-api`
- After unit edit: `sudo systemctl daemon-reload && sudo systemctl restart acme-api`
