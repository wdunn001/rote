---
slug: ssh-copy-id
name: ssh-copy-id (install your key)
family: net-ssh
platform: cross-platform
equivalents: 
references: man ssh-copy-id
---

# Command
```sh
ssh-copy-id [-i ~/.ssh/<key>.pub] <user>@<host>
```

# When to use
First-time setup of password-less SSH to a new host.

# When NOT to use
Host has password auth disabled — you need an alternative way to land the key (console, infra-as-code, snapshot, etc.).

# Gotchas
- The first time, you'll be prompted for the password (that's the point — it uses password auth to install the key, then future logins use the key).
- Picks the default key (`~/.ssh/id_rsa.pub` or `id_ed25519.pub`). Use `-i` to be explicit.
- Idempotent — re-running won't duplicate entries.
- If your shell on the remote is weird (no bash, custom prompt), `ssh-copy-id` may fail silently. Manually: `cat ~/.ssh/id_ed25519.pub | ssh user@host 'cat >> ~/.ssh/authorized_keys'`.

# Flags
- `-i <key.pub>`: specific public key
- `-p <port>`: non-22 SSH port
- `-o <ssh-opt>`: pass-through SSH options
- `-n`: dry-run (show what would be installed)

# Examples
- Standard: `ssh-copy-id user@edge-host`
- Specific key: `ssh-copy-id -i ~/.ssh/work_ed25519.pub work@host`
- Manual fallback: `cat ~/.ssh/id_ed25519.pub | ssh user@host 'mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'`
