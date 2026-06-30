---
slug: ssh-tunnel-local
name: ssh -L (local port forward)
family: net-ssh
platform: cross-platform
equivalents: 
references: man ssh
---

# Command
```sh
ssh -L <local-port>:<remote-host>:<remote-port> <user>@<gateway>
```

# When to use
Reach a service on the SSH server's network from your local machine. Connect to a remote DB from local psql; expose a edge-host service to a local browser; reach a service behind a corporate jumpbox.

# When NOT to use
You want OTHERS to reach a service on your machine — use `-R` (remote forward) instead.
Production proxying — use a real load balancer / proxy / VPN.

# Gotchas
- The tunnel is gone when the SSH session ends. For long-running, use `autossh` or `systemd-as-a-service`.
- `<remote-host>` is resolved on the SSH SERVER's network, not yours. `localhost` means 'localhost from the server's view'.
- Local port < 1024 needs root.
- `-N` (no command) + `-f` (background) makes a daemon tunnel without spawning a shell: `ssh -fN -L 5432:localhost:5432 user@host`.

# Flags
- `-L <lport>:<host>:<rport>`: local forward
- `-R <rport>:<host>:<lport>`: remote forward (server-side listen)
- `-D <port>`: dynamic SOCKS proxy
- `-N`: don't execute a remote command
- `-f`: background after auth
- `-T`: no PTY
- `-o ServerAliveInterval=60`: send keepalives (avoid corporate idle-kill)

# Examples
- Postgres on edge-host accessible locally: `ssh -fN -L 5432:localhost:5432 user@edge-host` then `psql -h localhost -p 5432`
- MetaMCP browser-reachable from this box: `ssh -fN -L 12008:localhost:12008 user@edge-host` then open http://localhost:12008/
- Tunnel through jumpbox to internal host: `ssh -L 8443:internal.host:443 user@jumpbox`
