---
slug: silent-install-windows-app-from-wsl
title: Silent install of a Windows .exe from a WSL shell — blocked by Defender + SmartScreen + UAC even when you do everything right
hit_count: 1
token_cost: high — hours of debug time chasing "Access denied" / "file in use" / no-output failures across cmd.exe, PowerShell, winget, and the installer itself, when the actual blockers are Windows-side and silent
---

# Symptom

Trying to install a Windows app (Ollama, VS Code, Node.js, etc.) silently from WSL using `cmd.exe /c installer.exe /SILENT` or `winget install --silent` keeps failing with one of:
- "Access is denied." (`exit=1`)
- "The process cannot access the file because it is being used by another process."
- A `winget install` process that runs for 5+ minutes and never reports progress, then has to be killed.
- An installer process (e.g. `OllamaSetup-fresh.tmp`) that runs for minutes with growing memory then plateaus and never produces an installed app.
- No installed binary appears under `%LocalAppData%\Programs\` or `Program Files\` despite the installer process running.

Verifying by checking:
- `Get-Process` shows the installer running, but
- `Get-ItemProperty HKLM:\...\Uninstall` / `HKCU:\...\Uninstall` shows no Ollama entry
- `where ollama` returns nothing
- API not bound

# Root cause

Multiple Windows protections layer up against a WSL-launched .exe:

1. **Windows Defender real-time scan** — first-time launch of a new exe triggers a deep scan (10–60 s). During that window the file is locked; `Start-Process` returns "file is being used by another process."
2. **SmartScreen / Mark of the Web** — files downloaded via WSL `curl` onto an NTFS path lack the Zone Identifier ADS that Windows uses to mark them safe-or-not. `Start-Process` returns "Access is denied."
3. **UAC propagation** — even for per-user installs to `%LocalAppData%`, some installers (or their bundled prerequisites like CUDA runtime) require elevation. UAC dialogs spawned by WSL-launched processes can hang invisibly because there's no foreground Windows session to surface them.
4. **Inno Setup silent install can stall** — `/SILENT /SUPPRESSMSGBOXES` is supposed to skip ALL prompts, but Ollama's installer in particular (post-0.24 era) bundles CUDA runtime extraction that can stall silently for reasons that don't surface in logs.
5. **winget UAC behavior** — `winget install` looks like it works (no error) but spawns a child elevated process that the launcher can't track; the WSL-side `winget` returns success while the actual install is still pending or failed.

The killer combo: any of these alone is recoverable.  Several together produce a state where the installer appears to "run" but never completes, killing it leaves zombie file locks, and you can't tell from the WSL side whether to wait or retry.

# Remedy

**The pragmatic short path:** open Explorer to the installer, let the user double-click it.

```bash
/mnt/c/Windows/explorer.exe "C:\\Users\\willi\\Downloads"
# tell the user: "click OllamaSetup-fresh.exe and click through the install"
```

The user-driven install handles UAC naturally; SmartScreen prompts on first launch and the user clicks Yes; Defender scans synchronously; the installer's UI surfaces any prompts that silent mode would have stalled on.

**The robust scripted path (when user isn't around):**

1. **Unblock the file** to clear MOTW:
   ```powershell
   Unblock-File -Path 'C:\Users\willi\Downloads\OllamaSetup.exe'
   ```
2. **Use winget** with NO `--silent` flag, OR with `--silent` PLUS the right `--scope user` and `--accept-source-agreements --accept-package-agreements` — let the installer prompt for UAC if it needs to:
   ```powershell
   winget install --id Ollama.Ollama --scope user --accept-package-agreements --accept-source-agreements
   ```
3. **For Inno Setup installers, use `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /LOG="...log"`** and inspect the log file after for what stalled.
4. **Give it 5 minutes** before assuming it's stuck. Defender first-launch scan + CUDA bundle extract genuinely take time.
5. **Don't kill the installer** mid-run unless you can see it's been idle (CPU = 0) for more than 60 s.  Killing leaves file locks that take a Windows session restart to clear.

For library scripts that want to attempt the silent path: try winget first; on failure within a timeout, surface a "please run installer interactively" message and open Explorer to the file.  See `scripts/install-ollama-windows-from-wsl.sh`.

# Detection

You're hitting this anti-pattern when:
- A silent installer run via cmd.exe or PowerShell from WSL exits 0 (or 1) but no software is installed.
- Memory of the installer process grows then plateaus and the daemon never comes up.
- `Get-Process` shows the .tmp installer running but registry has no Uninstall entry for the app.

# See also

- [[wsl-gpu-passthrough-check]] command — adjacent WSL-Windows bridge knowledge.
- [[wmic-from-wsl]] command — using Windows-side hardware enumeration from WSL.
- The script `scripts/install-ollama-windows-from-wsl.sh` — attempts the silent path and falls back to interactive when blockers surface.
