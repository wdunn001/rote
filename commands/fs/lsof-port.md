---
slug: lsof-port
name: lsof -i :PORT (what's listening on a port)
family: fs
platform: cross-platform
equivalents: ss -tlnp; netstat -tlnp (deprecated)
references: man lsof
---

# Command
```sh
lsof -i :<port>           # processes using this TCP/UDP port
lsof -i :<port> -sTCP:LISTEN  # just listeners
```

# When to use
'Port 5572 is already in use' — find what's bound. Debug 'why can't I connect to X'.

# When NOT to use
Production at scale — use `ss` (faster, kernel-native). `lsof` enumerates ALL open files first.

# Gotchas
- Without root, `lsof` only shows YOUR processes. Use `sudo lsof -i :PORT` for system-wide.
- `lsof -i :PORT` returns BOTH listeners and connections to that port. Use `-sTCP:LISTEN` to filter to just listeners.
- On macOS / WSL, the docker-internal-port might not show via lsof — use `docker ps` for those.

# Flags
- `-i :PORT`: by network port
- `-i TCP` / `-i UDP`: protocol
- `-i 4` / `-i 6`: IPv4 / IPv6
- `-n`: don't resolve IPs to hostnames (faster)
- `-P`: don't translate port numbers to names
- `-sTCP:LISTEN`: TCP state filter
- `+c0`: full command names (otherwise truncated to 9)

# Examples
- What's on 5572: `sudo lsof -i :5572 -nP`
- All listeners: `sudo lsof -i -sTCP:LISTEN -nP`
- A specific process's network: `lsof -i -a -p <pid>`
