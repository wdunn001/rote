---
slug: journalctl-follow
name: journalctl -u SERVICE -f (live tail systemd logs)
family: systemd
platform: debian, ubuntu, fedora, arch
equivalents: tail -f /var/log/<service>.log (legacy); docker logs -f (containers)
references: man journalctl
---

# Command
```sh
journalctl -u <unit> -f --since '5m ago'
```

# When to use
Tail / search logs of a systemd-managed service. Replaces tailing `/var/log/<unit>.log`.

# When NOT to use
Containers — those use the docker log driver. Get them via `docker logs` or the configured driver's destination.
Application-level structured logs you want to grep semantically — pipe through `jq` for JSON or use Loki/ELK.

# Gotchas
- Without `-u`, you see EVERYTHING. Always scope.
- `--since` and `--until` accept relative (`5m ago`, `2 days ago`) or absolute (`2026-01-15`) times.
- `journalctl` paginates with `less` by default. For piping, add `--no-pager` or `| cat`.
- High-volume services can produce GB of logs; journald defaults to a size cap (`SystemMaxUse` in journald.conf). Old logs vanish silently if not configured.

# Flags
- `-u <unit>`: scope to a service
- `-f`: follow
- `--since <time>`: from when
- `--until <time>`: until when
- `-n N`: last N lines (default `-n 10`)
- `-p err|warning|info|debug`: priority filter
- `-o json|json-pretty|short-iso|cat`: output format
- `-k`: kernel messages only
- `--no-pager`: don't run through less

# Examples
- Live tail: `journalctl -u acme-api -f`
- Last hour, errors only: `journalctl -u acme-api --since '1h ago' -p err`
- JSON for grepping: `journalctl -u acme-api -o json --no-pager | jq 'select(.PRIORITY <= "3")'`
