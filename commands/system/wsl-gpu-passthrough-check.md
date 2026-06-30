---
slug: wsl-gpu-passthrough-check
name: WSL2 GPU passthrough check (/dev/dxg + nvidia-smi)
family: system
platform: wsl-ubuntu
equivalents: (WSL-specific — no direct equivalent on native Linux)
references: https://learn.microsoft.com/windows/wsl/tutorials/gpu-compute
---

# Command
```sh
ls -la /dev/dxg                              # DirectX passthrough device node
nvidia-smi                                   # works inside WSL if passthrough is configured
ls -la /dev/nvidia*                          # CUDA character devices (modern builds)
ldconfig -p | grep libcuda                   # libcuda.so resolves to /usr/lib/wsl/lib/libcuda.so
```

# When to use
Before running any GPU workload inside WSL — Ollama, PyTorch, llama.cpp, sglang. Confirms the GPU is reachable from the Linux side.

The rote uses this to verify that a local Ollama install will actually have GPU acceleration available (CPU-only inference is much slower).

# When NOT to use
- Native Linux box — no need; the GPU is directly enumerated.
- macOS / Windows — different stacks.

# Gotchas
- `/dev/dxg` must exist for ANY GPU access from WSL. If it's missing: update WSL (`wsl --update`), update Windows GPU driver to a WSL-supporting version (NVIDIA: >= 470.x for CUDA; recent for full features), restart WSL (`wsl --shutdown` from Windows, then reopen).
- Inside WSL, `nvidia-smi` lives at `/usr/lib/wsl/lib/nvidia-smi`. It's a passthrough to the Windows driver — there is NO Linux NVIDIA driver in WSL. Don't install nvidia-driver-XXX packages.
- `libcuda.so` should resolve to `/usr/lib/wsl/lib/libcuda.so` (WSL passthrough); if it resolves to a /usr/lib/x86_64-linux-gnu copy, you may have installed a native Linux CUDA driver that conflicts. Remove it.
- WSL2 GPU memory is SHARED with the host — `nvidia-smi` shows total VRAM, but the Windows desktop, browser, games etc. compete for it.
- For Docker-in-WSL with GPU: `docker run --gpus all ...` works ONLY if you've installed `nvidia-container-toolkit` inside WSL.

# Flags
N/A — these are status checks, not commands with options.

# Examples
- Health check sequence:
  ```sh
  ls -la /dev/dxg && echo "WSL GPU passthrough device present"
  nvidia-smi && echo "NVIDIA driver passthrough working"
  ldconfig -p | grep -c libcuda && echo "libcuda symlinks present"
  ```
- Quick CUDA-capable test (needs python3 + a small CUDA-capable lib):
  ```sh
  python3 -c "import torch; print('cuda:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'n/a')"
  ```
- Restart pattern on errors: from a Windows cmd/powershell — `wsl --shutdown`, then reopen WSL. Don't try to restart the GPU driver from inside WSL; you can't.
