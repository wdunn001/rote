---
slug: docker-logs-follow
name: docker logs --tail N -f
family: container
platform: cross-platform
equivalents: kubectl logs -f --tail=N <pod>
references: https://docs.docker.com/engine/reference/commandline/logs/
---

# Command
```sh
docker logs --tail 100 -f <container>
```

# When to use
Live-tail the last N lines of a container's logs to debug a misbehaving service.

# When NOT to use
Log analysis at scale — pipe to a log aggregator (Loki, ELK, Splunk). The docker JSON-file driver isn't great at huge logs.

# Gotchas
- Default log driver is `json-file`; if you've set `journald`, `docker logs` may return nothing — use `journalctl CONTAINER_NAME=<name>`.
- `--tail all` shows the entire history; on a long-running container this can be GB.
- `--since 5m` and `--until 1m` (relative) or `--since 2026-01-15` (absolute) filter time ranges.
- Use `-t` to prefix each line with the timestamp (handy when correlating across logs).

# Flags
- `--tail N`: last N lines
- `-f` / `--follow`: stream new lines
- `-t` / `--timestamps`: prefix RFC3339 timestamps
- `--since <duration|time>`: relative or absolute start
- `--until <duration|time>`: relative or absolute end
- `--details`: include extra log driver metadata

# Examples
- `docker logs --tail 50 -f acme-api-1`
- Time window: `docker logs --since 10m --until 1m acme-rabbitmq-1`
- Timestamps: `docker logs -t --tail 100 acme-api-1 | grep ERROR`
