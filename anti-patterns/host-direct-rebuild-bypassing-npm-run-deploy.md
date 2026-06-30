---
slug: host-direct-rebuild-bypassing-npm-run-deploy
title: scp + docker compose up -d --build on the host breaks the nginx upstream
hit_count: 2
token_cost: critical — site goes down; user is mid-flow when 502s appear
---

# Symptom

You ssh to the prod host, `scp` a fresh tarball, run `docker compose up -d --build api`, the api container comes up healthy, but `app.acmefpv.com/api/*` starts returning **502 Bad Gateway** within seconds.

# Root cause

`acme-web-1`'s nginx caches the upstream api container's IP at container start. When you recreate `acme-api-1`, it gets a new IP on the docker network — nginx is still pointing at the old IP and tries to proxy to a dead address. The `npm run deploy` pipeline handles this end-to-end by also restarting `acme-web-1` after api is healthy; doing it host-direct skips that step.

The same anti-pattern hits other env-var-bound configurations: the deploy script injects per-environment variables (Authentik client secrets, Postgres connection strings, etc.) that aren't present when you build from a tarball on the host.

# Remedy

**Always** `npm run deploy` for server-side changes. From the repo root:

```bash
npm run deploy
```

The pipeline:
1. Builds containers locally
2. Pushes images to registry
3. SSH-orchestrates a coordinated container restart (api → web → workers) on the host
4. Runs migration check + health probes
5. Verifies the site is up before exiting

If you've already done a host-direct build and the site is down, the **hotfix** is:

```bash
ssh prod 'docker restart acme-web-1'
```

That's it. Web's nginx re-resolves the api upstream IP on restart.

# Detection

Anytime you find yourself typing `scp` or `docker compose up` on a prod host, **stop**. That's the smell. Use `npm run deploy`.

# See also

- [[feedback-always-npm-run-deploy]]
- [[feedback-work-not-done-until-deployed]]
