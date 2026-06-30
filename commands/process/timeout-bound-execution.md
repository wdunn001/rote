---
slug: timeout-bound-execution
name: timeout <seconds> <cmd> (kill if it runs too long)
family: process
platform: cross-platform
equivalents: gtimeout (mac, via brew install coreutils); manual sleep + kill
references: man timeout
---

# Command
```sh
timeout [<sig>] <duration> <cmd> [<arg>...]
```

# When to use
Bound how long a command can run. Critical for cron jobs, scripts that might hang on network, CI steps.

# When NOT to use
Production work — bake timeouts into the application code (HTTP client timeouts, connection pools, etc.). `timeout` is a coarse outer-layer guard.

# Gotchas
- Exit code 124 means 'timed out'. The rote run_script handler maps 124 to outcome 'timeout'.
- Default signal is SIGTERM. Use `-s SIGKILL` for processes that ignore SIGTERM.
- `--kill-after=<dur>` sends SIGKILL after additional <dur> if the original signal didn't work — belt + suspenders.
- macOS doesn't ship `timeout`; install with `brew install coreutils` (binary becomes `gtimeout`) or alias.

# Flags
- `-s` / `--signal=<sig>`: signal to send (default TERM)
- `-k` / `--kill-after=<dur>`: SIGKILL after extra <dur>
- `--preserve-status`: exit with the child's exit code, not 124 on timeout
- `--foreground`: don't make the child a separate process group

# Examples
- Bound a curl: `timeout 30 curl -fsS https://slow.host/`
- Reliably kill: `timeout -k 10 60 ./flaky-script.sh` (TERM after 60s; KILL 10s later if still alive)
- CI step: `timeout 1800 npm test || echo 'test suite timed out'` (kept inline; exit 124 on timeout)
