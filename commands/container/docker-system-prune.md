---
slug: docker-system-prune
name: docker system prune (free up disk)
family: container
platform: cross-platform
equivalents: podman system prune
references: https://docs.docker.com/engine/reference/commandline/system_prune/
---

# Command
```sh
docker system prune -af --volumes
```

# When to use
Reclaim disk space on a dev machine that's accumulated stopped containers, unused images, untagged dangling images, and abandoned volumes.

# When NOT to use
Production — almost certainly deletes things you care about. Run with smaller subcommands (`docker image prune`, `docker container prune`) and read the prompt first.

# Gotchas
- `-a` removes ALL unused images (not just dangling) — VERY aggressive.
- `--volumes` removes anonymous volumes too. If you have data in a volume but no running container is attached, it's gone.
- Always inspect first with `docker system df` to see what's eating space.
- Per-resource variants are safer: `docker image prune -a`, `docker container prune`, `docker volume prune` (NEVER `--volumes` on prod).

# Flags
- `-a` / `--all`: include unused images (not just dangling)
- `--volumes`: also remove volumes
- `-f` / `--force`: skip confirmation
- `--filter "until=24h"`: only resources older than 24h

# Examples
- Inspect first: `docker system df`
- Conservative: `docker system prune` (containers + dangling images + networks; no volumes)
- Aggressive (dev box): `docker system prune -af --volumes`
- Only old: `docker image prune -a --filter "until=168h"`
