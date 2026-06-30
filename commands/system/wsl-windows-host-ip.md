---
slug: wsl-windows-host-ip
name: Find the Windows host IP from inside WSL
family: system
platform: wsl-ubuntu
equivalents: (WSL-specific; no native-Linux equivalent because there's no host)
references: https://learn.microsoft.com/windows/wsl/networking
---

# Command
```sh
# Default route gateway -— the Windows host's WSL-bridge IP
ip route show | awk '/^default/ {print $3}'

# Nameserver from /etc/resolv.conf -— sometimes same, sometimes the DNS resolver
grep nameserver /etc/resolv.conf | awk '{print $2}' | head -1

# Windows hostname (from cmd.exe)
/mnt/c/Windows/System32/cmd.exe /c hostname | tr -d '\r\n' | tail -1
```

# When to use
You need to reach a Windows-side service from WSL but `localhost:PORT` doesn't work — usually because WSL2 localhost forwarding doesn't cover services bound to `127.0.0.1` only.

# When NOT to use
- `localhost:PORT` already works — don't add complexity.
- Windows 11 22H2+ with mirrored networking enabled — localhost IS the Windows localhost there; this whole problem class disappears.
- You're on native Linux — the "host" concept doesn't apply.

# Gotchas
- The default-route gateway IP is the WSL bridge's Windows side. This works for services bound to `0.0.0.0` on Windows. Services bound to `127.0.0.1` only are NOT reachable here regardless of firewall.
- `/etc/resolv.conf` nameserver in classic WSL2 networking points to the WSL DNS resolver (also a virtual IP), not the Windows host. Different IP from the gateway. The gateway is what you usually want for HTTP traffic.
- These IPs are EPHEMERAL across WSL restarts — don't hardcode them. Always discover at runtime.
- Mirrored networking mode (`networkingMode=mirrored` in `.wslconfig`) makes WSL share the Windows network stack — `localhost` works for everything. But also means no separate bridge IP exists.
- Windows hostname via `.local` mDNS (e.g. `DESKTOP-XXX.local`) usually doesn't resolve from WSL because Avahi/mDNS isn't running. Don't rely on it.

# Flags
N/A — these are read-only discovery commands.

# Examples
- Discover-then-use pattern:
  ```sh
  WIN_HOST=$(ip route show | awk '/^default/ {print $3}')
  curl -fsS "http://$WIN_HOST:11434/api/tags"
  ```
- Try localhost first, fall back to gateway:
  ```sh
  if curl -fsS -m 2 http://localhost:11434/api/tags >/dev/null; then
      OLLAMA="http://localhost:11434"
  else
      OLLAMA="http://$(ip route show | awk '/^default/ {print $3}'):11434"
  fi
  ```
- Check if mirrored networking is on (no gateway = mirrored):
  ```sh
  if ip route show | grep -q '^default'; then
      echo "classic WSL2 networking — gateway IP available"
  else
      echo "likely mirrored networking — localhost should reach Windows directly"
  fi
  ```
