---
slug: docker-inspect-format
name: docker inspect with --format
family: container
platform: cross-platform
equivalents: 
references: https://docs.docker.com/engine/reference/commandline/inspect/
---

# Command
```sh
docker inspect --format '{{.State.Status}} {{.State.Health.Status}}' <container>
```

# When to use
Scripted introspection of container state — health status, IPs, mounts, env vars.

# When NOT to use
Quick human-readable look — just `docker inspect` and read the JSON.

# Gotchas
- The Go template language is the format DSL. `{{.State.Health.Status}}` returns `<no value>` (literally) when the container has no HEALTHCHECK — handle that case in your script.
- `.HostConfig.PortBindings`, `.NetworkSettings.Networks`, `.Mounts` are the most useful subtrees.
- `docker inspect` accepts container OR image as the arg; same template DSL.

# Flags
- `--format <template>` / `-f`: Go template; emit specific fields
- `--size`: include disk usage info (containers)
- `--type container|image|volume|network`: explicit type

# Examples
- Container IP: `docker inspect -f '{{.NetworkSettings.IPAddress}}' <c>`
- All env vars: `docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' <c>`
- Bind mounts: `docker inspect -f '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}' <c>`
- Image SHA: `docker inspect -f '{{.Image}}' <c>`
