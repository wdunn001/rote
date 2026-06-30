---
slug: ssh-keygen-ed25519
name: ssh-keygen -t ed25519 (modern key)
family: net-ssh
platform: cross-platform
equivalents: 
references: man ssh-keygen
---

# Command
```sh
ssh-keygen -t ed25519 -C '<email-or-label>'
```

# When to use
Generating a new SSH keypair. Default to ed25519 — small, fast, secure.

# When NOT to use
Target system doesn't support ed25519 (very old OpenSSH < 6.5). Fall back to `-t rsa -b 4096`.

# Gotchas
- USE A PASSPHRASE. Without one, anyone with the file owns the key.
- Default output: `~/.ssh/id_ed25519` (private) + `~/.ssh/id_ed25519.pub` (public). Don't share the private file.
- The `-C` comment is just a label — typically your email or 'work-laptop'. Helps you identify keys later.
- For automation (CI keys), use a SEPARATE key with no passphrase, install it via secrets management, and restrict it via `authorized_keys` options (`command=...`, `restrict`).

# Flags
- `-t ed25519|rsa|ecdsa`: algorithm
- `-b <bits>`: key size (for RSA: 4096)
- `-C <comment>`: human label
- `-f <path>`: output path (default ~/.ssh/id_<type>)
- `-N <passphrase>`: passphrase non-interactively (CAREFUL — visible in shell history)
- `-a <rounds>`: KDF rounds (more = slower to brute-force)

# Examples
- Standard: `ssh-keygen -t ed25519 -C 'wdunn001@gmail.com'`
- RSA fallback for old systems: `ssh-keygen -t rsa -b 4096 -C 'legacy-vps'`
- Named: `ssh-keygen -t ed25519 -f ~/.ssh/work_github -C 'work-github-deploy'`
