---
slug: docker-exec-interactive
name: docker exec -it (interactive shell into container)
family: container
platform: cross-platform
equivalents: 
references: https://docs.docker.com/engine/reference/commandline/exec/
---

# Command
```sh
docker exec -it <container> bash   # or sh / zsh
```

# When to use
Debugging a running container — inspect filesystem, env vars, processes.

# When NOT to use
Persistent changes — they're lost on container recreate. Use a volume + edit on the host.
Production debugging — exec'ing into prod isn't an audit trail. Use logs + a sidecar pattern.

# Gotchas
- `bash` isn't installed in alpine-based images — use `sh`.
- `-it` (interactive + TTY) is what you want for a shell; `-i` alone for piping data; `-t` alone for log-only.
- Container must be RUNNING. To debug a crashed container, use `docker logs` or `docker run --rm --entrypoint sh <image>`.

# Flags
- `-i`: keep STDIN open
- `-t`: allocate a pseudo-TTY
- `-u <user>`: run as specific user (often `-u 0` for root debugging)
- `-w <dir>`: working directory
- `-e VAR=value`: env var for this exec session only

# Examples
- Root shell into a container: `docker exec -it -u 0 acme-api-1 bash`
- Run a one-off command: `docker exec acme-postgres-1 psql -U acme -c '\dt'`
