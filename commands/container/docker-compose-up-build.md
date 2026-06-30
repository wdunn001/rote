---
slug: docker-compose-up-build
name: docker compose up -d --build
family: container
platform: cross-platform
equivalents: 
references: https://docs.docker.com/compose/reference/up/
---

# Command
```sh
docker compose up -d --build [<service>...]
```

# When to use
After changing a Dockerfile or build context — forces image rebuild then brings the stack up detached.

# When NOT to use
Just a config change with no Dockerfile diff — use `docker compose up -d` (faster, no rebuild).
Production with downtime constraints — see the host-direct-rebuild anti-pattern; use the deploy pipeline that recreates the dependent container too (web nginx needs to re-resolve the api IP).

# Gotchas
- `--build` rebuilds EVERY service unless you name one. Targeting a single service: `docker compose up -d --build api`.
- Recreating an api container without restarting the nginx that proxies to it leaves nginx with the stale upstream IP — 502s. See anti-pattern `host-direct-rebuild-bypassing-npm-run-deploy`.
- For BuildKit DeadlineExceeded under load: prepend `COMPOSE_PARALLEL_LIMIT=1 COMPOSE_BAKE=false` and consider serial build (Acme's `DEPLOY_COMPOSE_BUILD_SERIAL=1`).

# Flags
- `-d` / `--detach`: run in background
- `--build`: rebuild images before starting
- `--force-recreate`: recreate containers even if config hasn't changed
- `--no-deps`: don't start linked services
- `--scale <svc>=N`: scale a service to N replicas
- `--remove-orphans`: remove services not in the current compose file

# Examples
- Full rebuild: `docker compose up -d --build`
- One service: `docker compose up -d --build api`
- Force recreate after env change: `docker compose up -d --force-recreate api`
