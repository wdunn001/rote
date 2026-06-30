---
slug: windows-set-env-from-wsl
name: Set Windows user / system env var from WSL via PowerShell
family: system
platform: wsl-from-windows
equivalents: export FOO=bar in .bashrc (Linux); setx (Windows cmd.exe — legacy)
references: about_Environment_Variables (PowerShell)
---

# Command
```sh
/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -Command \
    "[System.Environment]::SetEnvironmentVariable('OLLAMA_HOST', '0.0.0.0', 'User')"
```

# When to use
A Windows-side app needs a persistent env var (survives reboot). Common case: configure Ollama bind address, set proxy env vars, override default install paths for tools spawned from Windows shell.

# When NOT to use
- The env var only needs to live for one Process — use `$env:NAME = 'value'` in the same PowerShell session and launch the app from there.
- WSL-side processes — use `~/.bashrc` or `~/.profile`.
- You're inside an admin-protected environment where User env vars get reset by group policy.

# Gotchas
- The third argument is critical: `'User'`, `'Machine'` (system-wide, needs admin), or `'Process'` (current process only).
- Setting User env vars does NOT propagate to already-running processes. You must restart the target app (and any spawning shell) for it to see the new value.
- WSL processes don't inherit Windows env vars by default; this only affects Windows-side apps.
- `setx` (the legacy cmd.exe equivalent) truncates values at 1024 chars and has weird quoting; prefer `[System.Environment]::SetEnvironmentVariable`.

# Flags / forms
PowerShell call signature: `SetEnvironmentVariable(name, value, target)` where:
- `target = 'User'`: writes to `HKCU:\Environment` (per-user, no admin needed)
- `target = 'Machine'`: writes to `HKLM:\...\Session Manager\Environment` (system-wide, needs admin)
- `target = 'Process'`: just for the current PowerShell process

# Examples
- Set OLLAMA_HOST to bind all interfaces:
  ```powershell
  [System.Environment]::SetEnvironmentVariable('OLLAMA_HOST', '0.0.0.0', 'User')
  ```
- Read back to verify:
  ```powershell
  [System.Environment]::GetEnvironmentVariable('OLLAMA_HOST', 'User')
  ```
- Remove a User var:
  ```powershell
  [System.Environment]::SetEnvironmentVariable('OLLAMA_HOST', $null, 'User')
  ```
- System-wide (admin shell required):
  ```powershell
  [System.Environment]::SetEnvironmentVariable('PYTHONPATH', 'C:\my\lib', 'Machine')
  ```
- Legacy cmd.exe equivalent (for one-line scripts that can't load PowerShell):
  ```sh
  /mnt/c/Windows/System32/cmd.exe /c 'setx OLLAMA_HOST 0.0.0.0'
  ```
