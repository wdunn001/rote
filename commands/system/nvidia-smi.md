---
slug: nvidia-smi
name: nvidia-smi (NVIDIA GPU status + driver version)
family: system
platform: linux, wsl-ubuntu, windows
equivalents: rocm-smi (AMD); intel_gpu_top (Intel); Activity Monitor (macOS Metal)
references: man nvidia-smi
---

# Command
```sh
nvidia-smi             # one-shot table
nvidia-smi -l 1        # refresh every 1s (live monitor)
nvidia-smi dmon -s u   # dedicated utilization monitor
```

# When to use
First check on any NVIDIA-equipped box. Tells you: model, VRAM total/used/free, driver version, CUDA version, current temp/power, active compute processes.

The rote uses nvidia-smi to (1) detect that this machine has an RTX 2080 Ti before proposing local LLM hosting, (2) check VRAM headroom before deciding which model fits.

# When NOT to use
- Production monitoring at scale — use the NVIDIA DCGM exporter feeding Prometheus.
- Non-NVIDIA GPUs (AMD, Intel, Apple Silicon) — different tools.
- A GPU that's powered down or not enumerated — sometimes drivers need a reload (`sudo rmmod nvidia_uvm && sudo modprobe nvidia_uvm`).

# Gotchas
- Inside WSL2, `nvidia-smi` works because the Windows-side driver is exposed via `/dev/dxg`. If `/dev/dxg` is missing, WSL GPU passthrough isn't configured — the Windows driver needs to be a recent version (>= 470 for Linux CUDA, >= 510 for full WSL features).
- The `Driver Version` shown is the Windows driver version when running inside WSL. The `CUDA Version` shown is the MAX cuda the driver supports, not the runtime CUDA you have installed.
- `Persistence-M` `On`/`Off`: when Off, the driver unloads + reloads between uses (slow first call). Production GPU servers run `nvidia-smi -pm 1` once at boot to keep it persistent.
- The `Disp.A` column: `On` = this GPU drives the display. Display use eats VRAM (typically 1-6 GB depending on monitor + apps); the free column shows ACTUAL available for compute.

# Flags
- `-l <sec>` / `--loop=<sec>`: refresh every N seconds (live monitor)
- `-q` / `--query`: detailed per-GPU dump (much more than the table)
- `--query-gpu=<fields>`: scriptable field extraction (see nvidia-smi-query-csv command entry)
- `--query-compute-apps=<fields>`: what processes are using the GPU
- `-pm 1` / `-pm 0`: enable/disable persistence mode (needs root)
- `-i <gpu-idx>`: target a specific GPU on multi-GPU boxes
- `dmon -s <metrics>`: dedicated columnar live monitor (u=util, m=mem, c=clocks, t=temp)
- `pmon`: per-process columnar live monitor

# Examples
- Static check: `nvidia-smi`
- Live update: `watch -n 1 nvidia-smi` or `nvidia-smi -l 1`
- Just temperature: `nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader`
- Driver + CUDA from one line: `nvidia-smi --query-gpu=driver_version --format=csv,noheader`
- Production GPU server boot script: `sudo nvidia-smi -pm 1`
