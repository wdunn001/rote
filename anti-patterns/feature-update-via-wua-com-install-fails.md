---
slug: feature-update-via-wua-com-install-fails
title: Triggering a Windows feature upgrade via WUA COM IUpdateInstaller fails (ResultCode 4)
hit_count: 1
token_cost: medium - a feature update appears to "download (ResultCode 2)" then silently fails install (ResultCode 4), giving false confidence that the OS is being patched
---

# Symptom

Scripted Windows feature upgrade (e.g. 23H2 -> 25H2, KB5094126) via the Windows
Update Agent COM API:

```powershell
$s=New-Object -ComObject Microsoft.Update.Session
$d=$s.CreateUpdateDownloader(); $d.Updates=$coll; $d.Download()   # ResultCode=2 (Succeeded)
$i=$s.CreateUpdateInstaller();  $i.Updates=$coll; $i.Install()    # ResultCode=4 (FAILED), RebootRequired=False
```

Download reports success; Install returns OperationResultCode 4 (Failed) with no
pending-reboot flags set. The OS is NOT upgraded.

# Root cause

Feature updates (full OS version upgrades) are delivered through the Update
Orchestrator / UUP + a setup engine, not the classic `IUpdateInstaller` used for
cumulative/quality updates and drivers. `IUpdateInstaller.Install()` can enumerate
and "download" the feature update but cannot run the in-place setup, so it fails
(ResultCode 4). Quality updates, drivers, and defender defs DO install via this API;
feature updates do not.

OperationResultCode legend: 0 NotStarted, 1 InProgress, 2 Succeeded,
3 SucceededWithErrors, 4 Failed, 5 Aborted.

# Remedy

Use a method built for feature updates:
- **Windows 11 Installation Assistant** (official): `Windows11InstallationAssistant.exe
  /QuietInstall /SkipEULA` - performs the in-place upgrade to the latest version,
  then auto-reboots after staging (allow ~30+ min; less control over reboot timing).
- **ISO setup.exe** (most control): `setup.exe /auto upgrade /quiet /noreboot
  /dynamicupdate enable /copylogs <path>` - `/noreboot` lets you choose when to reboot.
- **Settings > Windows Update** (user-driven, most reliable for unattended-averse hosts):
  "Download & install" then "Restart now".

For quality/driver/defender updates, WUA COM (or `Update-MpSignature`) is fine.
Always verify a feature upgrade by build number after reboot
(`(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').CurrentBuild`),
never by the installer's return code alone.

# Detection

Feature-update Install() returning ResultCode 4 with RebootRequired=False and no
`...\Component Based Servicing\RebootPending` key = it did not stage. Distrust any
"OS is patching" claim that rests only on a WUA COM Install() call.

# See also

- [[rote]] skill
