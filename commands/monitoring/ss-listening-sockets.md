---
slug: ss-listening-sockets
name: ss -tlnp (listening TCP sockets + PID)
family: monitoring
platform: linux
equivalents: netstat -tlnp (deprecated); lsof -i :PORT (slower, more general)
references: man ss
---

# Command
```sh
ss -tlnp
```

# When to use
Quick: what's listening on what TCP port, owned by which process. Modern replacement for `netstat -tlnp`.

# When NOT to use
macOS — `ss` isn't standard; use `lsof -iTCP -sTCP:LISTEN -nP`.

# Gotchas
- `-p` (process) needs root to show PIDs from other users.
- `-n` skips DNS / port-name resolution — much faster on busy boxes.
- `-t` for TCP, `-u` for UDP, `-l` for listening only, `-a` for all states.
- Drop `-l` to see established connections too: `ss -tnp`.

# Flags
- `-t` / `-u`: TCP / UDP
- `-l`: listening only
- `-n`: numeric (no DNS)
- `-p`: show owning process (needs root for full info)
- `-a`: all states (including TIME_WAIT, CLOSE_WAIT)
- `-4` / `-6`: address family
- `state established`: filter by socket state

# Examples
- All listeners: `sudo ss -tlnp`
- Specific port: `sudo ss -tlnp 'sport = :5572'`
- Connections to a host: `sudo ss -tn 'dst edge-host'`
- TCP states summary: `ss -s`
