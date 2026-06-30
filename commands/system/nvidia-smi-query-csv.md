---
slug: nvidia-smi-query-csv
name: nvidia-smi --query-gpu / --query-compute-apps (scriptable GPU state)
family: system
platform: linux, wsl-ubuntu, windows
equivalents: rocm-smi --showuse (AMD)
references: nvidia-smi --help-query-gpu
---

# Command
```sh
nvidia-smi --query-gpu=<fields> --format=csv[,noheader][,nounits]
nvidia-smi --query-compute-apps=<fields> --format=csv[,noheader]
```

# When to use
Scripted GPU state — feed VRAM/temp/util into monitoring, conditional logic, or a delegate-registry health check.

# When NOT to use
- Human inspection — the plain `nvidia-smi` table is more readable.
- Sub-second polling — nvidia-smi's startup is ~50ms; consider DCGM for high-frequency.

# Gotchas
- `--format=csv,noheader` strips the header row — handy for piping to other tools.
- `--format=csv,nounits` strips ` MiB`, ` %`, ` C` etc. suffixes — needed when piping to `awk` / `bc` for arithmetic.
- `--query-compute-apps` shows PROCESSES using the GPU. The rote uses this to verify "is anything actually loaded onto the GPU right now?" before estimating free VRAM.
- Some fields require root or specific permissions (e.g. `--query-supported-clocks`).

# Flags
- `--query-gpu=<comma-sep-fields>`: per-GPU snapshot
- `--query-compute-apps=<comma-sep-fields>`: per-process accounting
- `--query-accounted-apps=<...>`: historical (needs accounting mode `nvidia-smi --accounting-mode=1`)
- `--query-supported-clocks=<...>`: supported GPU clock combinations

Common --query-gpu fields:
- `name`, `uuid`, `serial`, `driver_version`, `vbios_version`
- `memory.total`, `memory.used`, `memory.free`
- `utilization.gpu`, `utilization.memory`
- `temperature.gpu`, `power.draw`, `power.limit`
- `compute_cap`, `pstate`, `clocks.current.sm`

Common --query-compute-apps fields:
- `pid`, `process_name`, `used_memory`
- `gpu_uuid`, `gpu_serial`

# Examples
- VRAM in MB only: `nvidia-smi --query-gpu=memory.free,memory.used,memory.total --format=csv,nounits`
- Util + temp loop: `nvidia-smi --query-gpu=utilization.gpu,temperature.gpu --format=csv,noheader -l 2`
- Which PIDs own VRAM: `nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv`
- Conditional: `[[ $(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits) -gt 8000 ]] && ollama run llama3.1:8b`
- JSON-friendly tabular dump: `nvidia-smi --query-gpu=index,name,memory.free,memory.used,utilization.gpu --format=csv,noheader`
