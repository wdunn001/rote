---
slug: apt-get-install-with-update
name: apt-get install (with update first)
family: package-mgmt
platform: debian, ubuntu, wsl-ubuntu
equivalents: dnf install (fedora); brew install (macos); choco install (windows); apk add (alpine); pacman -S (arch)
references: man apt-get; https://manpages.debian.org/apt-get
---

# Command
```sh
apt-get update && apt-get install -y <package> [<package>...]
```

# When to use
Non-interactive package install in scripts, Dockerfiles, CI.

# When NOT to use
Interactive shell — use `apt install` (friendlier UI, same backend). You just ran `apt-get update` — skip the chain.

# Gotchas
- WITHOUT the `&& apt-get update` you can get stale apt cache: 'package not found' or wrong-version installs.
- `-y` is essential non-interactively; without it the install hangs on the first confirmation prompt.
- Use `apt-get` (NOT `apt`) in scripts. `apt` itself warns 'do not use in scripts' because its CLI is unstable.
- `--no-install-recommends` can drastically cut install size and prevent surprise dependencies.
- Run as root (or via sudo) — apt-get will refuse otherwise.

# Flags
- `-y` / `--yes`: auto-answer yes to all prompts
- `--no-install-recommends`: skip Recommended deps (smaller install)
- `--no-install-suggests`: skip Suggested deps
- `-q` / `--quiet`: less output (use in CI)
- `--reinstall`: force re-install even if already present
- `-o Dpkg::Options::="--force-confnew"`: keep new config files on conflict

# Examples
- Dockerfile: `RUN apt-get update && apt-get install -y --no-install-recommends curl jq && rm -rf /var/lib/apt/lists/*`
- One-liner: `sudo apt-get update && sudo apt-get install -y postgresql-client`
