---
slug: com-hkcu-phantom-clsid-noise
title: Treating HKCU COM InprocServer32 entries with missing DLLs as persistence
hit_count: 1
token_cost: high - a single bad "phantom-target" rule turned a persistence sweep into thousands of false positives (3,700+), drowning the real findings
---

# Symptom

A Windows persistence/ASEP hunter flags thousands of "HIGH-confidence" items, the
vast majority being `HKCU\SOFTWARE\Classes\CLSID\{...}\InprocServer32` entries
whose target DLL no longer exists on disk (reason: "phantom / target-missing").
Real signals (IFEO debuggers, AppInit, WMI consumers, LOLBin tasks) are buried.

# Root cause

Two compounding mistakes:
1. **COM CLSID registrations are a stale-registration swamp.** Uninstalled software
   routinely leaves orphaned per-user COM classes behind. A classic example is the
   Java Plug-in `CAFEEFAC-*` CLSIDs pointing at an uninstalled
   `C:\Program Files\Java\jre1.8.0_341\bin\jp2iexp.dll` - dozens to hundreds of them,
   all benign.
2. **"Target DLL missing" was put in the HARD (rarely-benign) reason list.** For
   Run keys / Services / Scheduled Tasks a missing target can be meaningful; for
   COM InprocServer32 it is overwhelmingly benign leftover.

# Remedy

- Do NOT promote `phantom/target-missing` to high-confidence for COM-HKCU entries.
  Scope "phantom" promotion to `Run:* / Service* / Task* / Winlogon / StartupFolder`.
- Treat per-user COM hijack as high-signal only when the InprocServer32 DLL is
  PRESENT and (a) unsigned/non-publisher-matching AND (b) in a user-writable path
  AND (c) the same CLSID also exists under HKLM (i.e. an actual shadow/override).
- Keep COM-HKCU in the raw collection (low false-negative), but exclude it from the
  triage shortlist by default; surface only the present+writable+shadowing subset.

# Detection

Persistence sweep where >90% of "suspects" share a single reason and a single
Category prefix (`COM-HKCU-InprocServer32`) and point at one uninstalled vendor dir.

# See also

- [[rote]] skill
- win-hunt-persistence.ps1 / win-hunt-triage.ps1 (win-threat-hunt family)
