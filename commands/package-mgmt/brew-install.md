---
slug: brew-install
name: brew install (macOS)
family: package-mgmt
platform: macos
equivalents: apt-get install (debian/ubuntu); dnf install (fedora); choco install (windows); apk add (alpine)
references: https://docs.brew.sh/
---

# Command
```sh
brew install <formula> [<formula>...]
```

# When to use
Install CLI tools and libraries on macOS.

# When NOT to use
GUI apps — use `brew install --cask <cask>` instead. System Python packages — use pyenv / asdf / nix.

# Gotchas
- Homebrew updates ALL formulas during `brew update`; the install command no longer auto-runs update (it used to). Run `brew update` first if you want the latest formula.
- Bottle (prebuilt) downloads are fast; building from source can be very slow on big formulas (e.g. ffmpeg, gcc).
- On Apple Silicon, brew installs to `/opt/homebrew`; on Intel, to `/usr/local`. Scripts that hardcode paths break across architectures.

# Flags
- `--cask`: GUI/desktop app instead of CLI formula
- `--HEAD`: build from tip of master (no bottle)
- `-v` / `--verbose`: show what's happening
- `--only-dependencies`: install deps but not the formula itself

# Examples
- `brew install jq fd ripgrep`
- `brew install --cask iterm2`
