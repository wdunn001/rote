---
slug: lspci-gpu
name: lspci | grep -i VGA (any-vendor GPU enumeration)
family: system
platform: linux, wsl-ubuntu
equivalents: system_profiler SPDisplaysDataType (macOS); Get-PnpDevice -Class Display (Windows PowerShell)
references: man lspci
---

# Command
```sh
lspci | grep -iE 'vga|display|3d'
lspci -nnvv -s <slot>     # full detail for a specific slot
```

# When to use
Identify ANY GPU regardless of vendor (NVIDIA, AMD, Intel, virtualization). Works without vendor-specific drivers — reads PCI device IDs directly.

The rote used this to discover what video card is on the WSL machine. `nvidia-smi` only sees NVIDIA; `lspci` sees everything plugged in.

# When NOT to use
- Inside WSL2 — `lspci` typically shows nothing because the GPU is bridged via DirectX/dxg, not exposed as a real PCI device. Use `nvidia-smi` (inside WSL) or `wmic` (against the Windows host) instead.
- macOS — different tooling (`system_profiler`).

# Gotchas
- WSL2 reports "no PCI VGA visible" even when a GPU is fully usable via DirectX passthrough. This is because the GPU isn't enumerated as a Linux PCI device — it's a paravirtualized device accessed via `/dev/dxg`. See the wsl-gpu-passthrough-check command.
- `-nn` shows numeric vendor:device IDs alongside the human name — useful for googling obscure cards.
- `-vv` gives extreme verbose output including capabilities, MSI config, etc.
- The PCI slot column (e.g. `07:00.0`) is what other tools need (`nvidia-smi -i 0`).

# Flags
- `-n`: numeric IDs only (no name lookup)
- `-nn`: both numeric AND name
- `-v` / `-vv` / `-vvv`: increasing verbosity
- `-s <slot>`: filter to a specific slot
- `-d <vendor>:<device>`: filter by vendor:device ID
- `-k`: show kernel driver in use + module name

# Examples
- All GPUs (any vendor): `lspci | grep -iE 'vga|display|3d'`
- Detailed including driver: `lspci -nnk | grep -A3 -iE 'vga|display|3d'`
- Filter NVIDIA only: `lspci -d 10de:`  (10de = NVIDIA's PCI vendor ID)
- Detailed for a specific slot: `lspci -nnvv -s 07:00.0`
