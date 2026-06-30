---
slug: pkill-f-kills-own-shell
title: pkill -f <pattern> killed the shell running pkill
hit_count: 1
token_cost: low — one lost command + confusion
---

# Symptom

Ran `pkill -f 'translate-i18n-via-delegate'` to stop background node runs. The command itself died (exit 144 = SIGTERM), and subsequent steps in the same command never ran.

# Root cause

`pkill -f` matches against the **entire command line** of every process — including the `bash -c "...pkill -f 'translate-i18n-via-delegate'..."` wrapper that is currently executing, because that wrapper's command line contains the pattern string. So pkill signals itself.

# Remedy

- Inspect first: `pgrep -af '<pattern>'` and kill specific PIDs you've confirmed are the targets.
- Or stop harness-tracked background jobs with `TaskStop <task-id>`.
- Or ask Ollama to unload a model directly: `curl .../api/generate -d '{"model":"X","keep_alive":0}'`.
- Never `pkill -f <pattern>` when the pattern also matches the command you're running.
