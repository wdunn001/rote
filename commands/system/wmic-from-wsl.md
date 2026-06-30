---
slug: wmic-from-wsl
name: wmic.exe via /mnt/c (Windows hardware enumeration from WSL)
family: system
platform: wsl-ubuntu
equivalents: PowerShell Get-CimInstance / Get-ComputerInfo (modern Windows); dmidecode (Linux native)
references: https://learn.microsoft.com/windows/win32/wmisdk/wmic
---

# Command
```sh
/mnt/c/Windows/System32/wbem/WMIC.exe path win32_VideoController get name
/mnt/c/Windows/System32/wbem/WMIC.exe cpu get name,NumberOfCores,MaxClockSpeed
/mnt/c/Windows/System32/wbem/WMIC.exe path win32_PhysicalMemory get capacity
```

# When to use
You're inside WSL but need to inspect Windows-side hardware (GPU model, CPU, RAM, BIOS, disks).  `lspci` doesn't enumerate WSL-bridged devices; `wmic` queries Windows directly.

The rote used this to confirm "NVIDIA GeForce RTX 2080 Ti" as the Windows-side GPU when proposing local LLM hosting.

# When NOT to use
- You're on native Linux — use `lshw`, `lspci`, `dmidecode` instead.
- You're on a Windows shell directly — just use the executables in PATH.
- You want a fast scripted Windows query — WMIC is deprecated and slow; prefer `pwsh.exe -Command 'Get-CimInstance ...'` if PowerShell 7 is installed Windows-side.

# Gotchas
- WMIC IS DEPRECATED by Microsoft since Windows 10 21H1. Still ships in current Windows but won't get new features. Modern replacement: PowerShell `Get-CimInstance`.
- From WSL the full path is needed because `wmic.exe` isn't on $PATH by default. Add `/mnt/c/Windows/System32/wbem/` to PATH if you use it often.
- WMIC output is sometimes mangled (extra CR-LF, fixed-width columns); pipe through `tr -d '\r'` and `awk '{$1=$1};1'` to normalize for further processing.
- WMIC can also act on REMOTE hosts: `wmic.exe /node:<hostname> ...` — handy for inventory but rarely needed from WSL.

# Flags
- `path <class>`: WMI class to query (e.g. win32_VideoController, win32_PhysicalMemory)
- `get <fields>`: comma-sep list of fields
- `where "<filter>"`: WHERE-style filter
- `/format:list` or `/format:csv`: output format
- `/node:<host>`: remote query

# Examples
- GPU model: `/mnt/c/Windows/System32/wbem/WMIC.exe path win32_VideoController get name`
- CPU: `/mnt/c/Windows/System32/wbem/WMIC.exe cpu get name,numberofcores,maxclockspeed /format:list`
- All RAM modules: `/mnt/c/Windows/System32/wbem/WMIC.exe memorychip get capacity,speed,manufacturer`
- BIOS: `/mnt/c/Windows/System32/wbem/WMIC.exe bios get manufacturer,smbiosbiosversion`
- Storage: `/mnt/c/Windows/System32/wbem/WMIC.exe diskdrive get model,size,interfacetype`

PowerShell modern equivalents (if PowerShell 7 is installed on Windows):
- GPU: `pwsh.exe -Command 'Get-CimInstance Win32_VideoController | Select Name'`
- CPU: `pwsh.exe -Command 'Get-CimInstance Win32_Processor | Select Name,NumberOfCores,MaxClockSpeed'`
