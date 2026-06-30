---
slug: msi-source-absent-1612-localpackage-restore
title: MSI uninstall/upgrade fails 1612 (source absent) - restore the cached LocalPackage to fix
hit_count: 1
token_cost: high - blocks every uninstall/upgrade path (msiexec /x GUID, /x file, winget, in-place upgrade Error 1714) until the cache is restored; easy to waste many attempts
---

# Symptom

`msiexec /x {ProductCode}` -> **1612** (ERROR_INSTALL_SOURCE_ABSENT). winget
uninstall -> 1612. `msiexec /x <freshly-downloaded.msi>` -> still 1612. An in-place
upgrade (newer MSI) -> **1603**, with the verbose log showing
`Error 1714. The older version ... cannot be removed ... System Error 1612` during
`RemoveExistingProducts`. The product cannot be removed or upgraded by any normal means.

Often appears across MANY products on one host (e.g. Node.js, VirtualBox, Pulse) =
a systemically pruned `C:\Windows\Installer` cache (disk-cleanup tools, "free space"
utilities, or migration drop the cached MSIs that Windows Installer needs for
every future uninstall/repair).

# Root cause

Windows Installer keeps a cached copy of each product's MSI at a path recorded in
`HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Installer\UserData\<SID>\Products\
<packed-guid>\InstallProperties\LocalPackage` (e.g. `C:\Windows\Installer\1a7ef9e1.msi`).
Uninstall/repair/RemoveExistingProducts all need that cached package. If the file is
gone, msiexec reports the source as absent (1612) - and `/x <some-other-file.msi>`
does NOT help unless that file's ProductCode AND the registered LocalPackage path
both line up.

# Remedy (cache-restore)

1. Get the product's ProductCode (from the Uninstall key's UninstallString).
2. Obtain an MSI with the SAME ProductCode:
   - download the exact same version from the vendor (e.g. nodejs.org/dist/vX/...msi), OR
   - for combined EXE installers, extract it: `installer.exe --extract -path <dir> --silent`
     (VirtualBox), then verify ProductCode:
     `$wi=New-Object -ComObject WindowsInstaller.Installer; $db=$wi.OpenDatabase($msi,0);
      $v=$db.OpenView("SELECT Value FROM Property WHERE Property='ProductCode'"); $v.Execute();
      $v.Fetch().StringData(1)`
3. Find the registered LocalPackage path (enumerate `...\Installer\UserData\*\Products\*\
   InstallProperties` where `DisplayName` matches) and **copy the matching MSI to that
   exact path** (overwrite the missing file).
4. Now `msiexec /x {ProductCode} /qn /norestart` succeeds (exit 0). For an upgrade,
   the new installer's RemoveExistingProducts can also now remove the old one.

ONLY restore with a same-ProductCode MSI - a mismatched package will be rejected
(1605/1606) or, worse, misapplied. Verify the ProductCode before copying.

# Fallback (no matching MSI obtainable, e.g. Pulse/Ivanti gated downloads)

- Neutralize the attack surface instead of removing: stop + disable the product's
  services/kernel drivers (`sc.exe stop`, `sc.exe config <name> start= disabled`) -
  removes the exploitable surface even if the product entry lingers.
- Use the Microsoft "Program Install and Uninstall Troubleshooter" (.diagcab) to
  force-remove the broken product registration.

# Detection

Any uninstall returning 1612, or an upgrade log with `Error 1714 ... System Error 1612`.
Confirm by reading the product's LocalPackage value and `Test-Path` it (missing = this).

# See also

- [[rote]] skill
- [[feature-update-via-wua-com-install-fails]]
