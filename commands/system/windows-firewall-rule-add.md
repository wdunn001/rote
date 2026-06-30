---
slug: windows-firewall-rule-add
name: New-NetFirewallRule (open an inbound port on Windows)
family: system
platform: windows, wsl-from-windows
equivalents: ufw allow <port> (Linux); pf table (macOS)
references: Get-Help New-NetFirewallRule
---

# Command
```sh
# From WSL via PowerShell:
/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command \
    "New-NetFirewallRule -DisplayName 'Ollama API (11434)' -Direction Inbound -Protocol TCP -LocalPort 11434 -Action Allow -Profile Any"
```

# When to use
You're exposing a Windows-hosted service on a specific port and need WSL — or another LAN host — to reach it. Common case: Ollama, sglang, or any locally-installed daemon that binds 0.0.0.0 (or you want reachable from WSL).

The rote uses this to make Windows-side Ollama reachable from WSL at port 11434.

# When NOT to use
- Native Linux — use `ufw`, `iptables`, or `nft`.
- macOS — different stack (`pf`).
- You don't actually want LAN inbound — the service should bind localhost only.
- You're inside a corporate environment where firewall rules are managed by GPO; your local rule won't override.

# Gotchas
- New-NetFirewallRule REQUIRES ELEVATION. From a non-admin PowerShell session, this throws "Access is denied." You need an admin-elevated shell, OR add the rule from the Windows Firewall GUI manually then add `--skip-firewall` to library scripts.
- `-Profile Any` is broad. Use `-Profile Private` if you only need it reachable from your LAN.
- If you set OLLAMA_HOST=0.0.0.0 (or any bind-all), the firewall rule is required even for LOOPBACK from WSL — because WSL2's bridge interface is treated as a separate network adapter.
- Rules persist across reboots. To remove: `Remove-NetFirewallRule -DisplayName '...'`.
- `Get-NetFirewallRule -DisplayName '...'` shows existing rules; idempotent scripts should check first to avoid duplicates.

# Flags / parameters
- `-DisplayName <text>`: human-readable name (used to query/remove later)
- `-Direction Inbound|Outbound`
- `-Protocol TCP|UDP|ICMPv4|ICMPv6|Any`
- `-LocalPort <port>` / `-RemotePort <port>`
- `-Action Allow|Block`
- `-Profile Any|Domain|Private|Public` (which network locations)
- `-Program <path>`: scope to a specific .exe
- `-LocalAddress <addr>`: scope to a specific local IP (e.g. WSL bridge subnet only)
- `-Enabled True|False`: create disabled

# Examples
- Open a port for Ollama:
  ```powershell
  New-NetFirewallRule -DisplayName 'Ollama API (11434)' -Direction Inbound -Protocol TCP -LocalPort 11434 -Action Allow -Profile Any
  ```
- Idempotent (check first):
  ```powershell
  if (-not (Get-NetFirewallRule -DisplayName 'Ollama API (11434)' -ErrorAction SilentlyContinue)) {
      New-NetFirewallRule -DisplayName 'Ollama API (11434)' -Direction Inbound -Protocol TCP -LocalPort 11434 -Action Allow -Profile Any
  }
  ```
- Open for ONE app only (more restrictive than port-based):
  ```powershell
  New-NetFirewallRule -DisplayName 'Ollama app' -Direction Inbound -Program 'C:\Users\willi\AppData\Local\Programs\Ollama\ollama app.exe' -Action Allow -Profile Any
  ```
- Remove: `Remove-NetFirewallRule -DisplayName 'Ollama API (11434)'`
- List Ollama-related rules: `Get-NetFirewallRule -DisplayName '*Ollama*' | Format-Table DisplayName,Action,Enabled`
