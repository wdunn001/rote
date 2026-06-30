---
slug: curl-fssL
name: curl -fsSL (the script-friendly curl)
family: net-ssh
platform: cross-platform
equivalents: wget -qO-
references: man curl
---

# Command
```sh
curl -fsSL <url>
```

# When to use
Fetch content from a URL in a script. The `-fsSL` flag set is what you almost always want.

# When NOT to use
Need progress display for a human — drop `-s`. Want interactive auth prompts — that's `-u`.

# Gotchas
- `-f`: fail on HTTP 4xx/5xx (otherwise curl exits 0 even on a 500). WITHOUT this, your script silently succeeds on broken downloads.
- `-s`: silent (no progress/error meter). With ONLY `-s`, errors are silent — that's why we add `-S` (show errors despite -s).
- `-L`: follow redirects. Without it, a 301 returns the redirect HTML, not the target.
- For piping into shell (`curl ... | sh`) — DON'T. Inspect first. If you must, at minimum verify with a checksum.

# Flags
- `-f` / `--fail`: non-zero exit on HTTP error
- `-s` / `--silent`: no progress meter
- `-S` / `--show-error`: show errors despite -s
- `-L` / `--location`: follow redirects
- `-o <file>` / `--output`: save to file
- `-O`: save to filename from URL
- `-m <sec>` / `--max-time`: total timeout
- `--connect-timeout <sec>`: TCP-establish timeout
- `-H 'Header: value'`: custom header
- `-d '<body>'`: POST body
- `-X POST|PUT|...`: explicit method
- `-u user:pass`: HTTP basic auth

# Examples
- Healthcheck: `curl -fsS -m 5 http://localhost:5572/healthz`
- POST JSON: `curl -fsS -X POST -H 'Content-Type: application/json' -d '{"k":1}' http://api/v1/foo`
- Download to disk: `curl -fsSLO https://example.com/file.tar.gz`
- With timeout + retry-ish: `curl -fsSL --max-time 30 --connect-timeout 5 <url>`
