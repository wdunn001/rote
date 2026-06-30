---
slug: writable-path-probe-as-admin-false-positive
title: Testing PATH-directory writability while elevated reports every dir as writable
hit_count: 1
token_cost: medium - produces a long bogus "privilege-escalation surface" list that wastes triage time and can mislead a report
---

# Symptom

A Windows threat-hunt / privesc check that probes each `PATH` directory for write
access (phantom-DLL planting, writable service binaries) by trying to create a
temp file returns a HUGE list of "writable" directories - including
`C:\Windows\System32`, `C:\Program Files\...`, etc. The finding looks alarming
(dozens of writable PATH dirs) but is an artifact of HOW it was run.

# Root cause

The probe ran in an **elevated / Administrator** context. An admin token can write
almost anywhere, so a "can I create a file here?" test trivially succeeds in every
directory. Writable-PATH / weak-ACL findings are only meaningful for a
**non-administrative** principal - that is who an attacker is when hunting for a
privilege-escalation primitive.

# Remedy

- Re-run the writability check as a **standard (non-admin) user**, OR
- Evaluate the DACL explicitly instead of probing: read `Get-Acl <dir>` and check
  for write/modify/createfiles rights granted to non-privileged SIDs
  (`Everyone` S-1-1-0, `Authenticated Users` S-1-5-11, `Users` S-1-5-32-545,
  the interactive user) - ignore grants to `Administrators`/`SYSTEM`/`TrustedInstaller`.
- In reports, always record the privilege context a check ran under; a privesc
  finding gathered as admin is not a finding.

# Detection

Any "writable directory / weak ACL / writable service binary" result set that
includes `System32`, `Program Files`, or `Windows` is the tell. If the hunt was
launched from an elevated shell (e.g. "Administrator:" in the title), distrust the
whole writability dimension until re-run unprivileged.

# See also

- [[rote]] skill
- win-hunt-dll-hijack.ps1 / win-vuln-config-audit.ps1 (win-threat-hunt + vuln-scanner families)
