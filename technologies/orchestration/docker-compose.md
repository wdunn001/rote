---
slug: docker-compose
name: Docker Compose
category: orchestration
implements_patterns: infrastructure-as-code
tags: self-hosted, offline-capable, open-source
references: https://docs.docker.com/compose/
---

# When to use
Local-dev or small-prod orchestration (single host).

Multi-service apps where Kubernetes is overkill.

Acme's deploy.cjs ships docker compose stacks for prod.

# When NOT to use
Multi-host / multi-region orchestration — use Kubernetes / Nomad.

You need rolling updates with zero-downtime invariants out of the box — Compose's update flow is basic.

# Limitations
- Single host (or use Swarm which is dead-end).
- Healthcheck dependencies (depends_on: condition: service_healthy) work but are fragile.
- No declarative drift detection.

# Cost
Free.

# Alternatives
Kubernetes (heavy but multi-host).  Nomad (lighter than K8s).  Plain systemd (single host, no containers).
