---
slug: adb-crash-buffer-rootcause
name: adb logcat crash buffer — fastest RN/Android native crash root cause
language: bash
applies_patterns:
applies_technologies: adb, android
references: reference_windows_tools_from_wsl
---

# When to use
A React Native / Expo (or any Android) app crashes and you need the actual NATIVE
FATAL stack. JS try/catch can't catch native service/thread crashes (e.g. a
foreground-service start SecurityException), so they don't show in Metro. The
dedicated crash buffer PERSISTS the last FATAL across process death.

# When NOT to use
Pure JS errors — those are in the Metro / ReactNativeJS log, not the crash buffer.

# Placeholders
- ADB: path to adb (WSL: /mnt/c/Users/<user>/AppData/Local/Android/Sdk/platform-tools/adb.exe)
- SERIAL: device serial from `adb devices` (example: R5CX22MFTVX)
- MARKER: a class/keyword to anchor on (example: SecurityException, your package, FATAL)

# Snippet
"${ADB}" -s "${SERIAL}" logcat -b crash -d -t 300 \
  | grep -iA30 "FATAL EXCEPTION\|AndroidRuntime\|${MARKER}"
# -b crash = the dedicated crash buffer (survives the process death); -d = dump+exit.
# This one command surfaced the exact FGS "Starting FGS with type microphone …
# requires RECORD_AUDIO" SecurityException — root cause in one shot vs hours of
# theorizing. From WSL, adb is the Windows-side binary (see memory).
