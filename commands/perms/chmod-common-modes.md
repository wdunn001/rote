---
slug: chmod-common-modes
name: chmod common modes (600, 644, 700, 755)
family: perms
platform: cross-platform
equivalents: icacls (windows); chmod is also on macOS/BSD with minor differences
references: man chmod
---

# Command
```sh
chmod 600 <file>   # owner rw, others nothing — secrets/keys
chmod 644 <file>   # owner rw, world read — docs/configs
chmod 700 <dir>    # owner rwx, others nothing — ~/.ssh
chmod 755 <file>   # owner rwx, world rx — scripts/binaries
```

# When to use
Set Unix file permissions. The four common modes cover ~95% of needs.

# When NOT to use
ACL-based perms (`setfacl`); SELinux labels; Windows ACLs (`icacls`).
WSL on drvfs (`/mnt/[a-z]/`) — `chmod` is a no-op there. See anti-pattern `silent-chmod-noop-on-drvfs`.

# Gotchas
- `chmod 0777` on a secrets file is a recurring security mistake. The user's `deploy.env` was 0777; see the perms remediation in the acme docs.
- `chmod -R` is RECURSIVE. Use carefully — chmod 600 on a tree breaks every dir's traversal (dirs need x to enter).
- `find . -type f -exec chmod 644 {} +` then `find . -type d -exec chmod 755 {} +` is the safe way to reset perms across a tree.
- WSL drvfs ignores chmod. The file mode reports as 0777 always. You need Windows ACLs or `/etc/wsl.conf` metadata.

# Flags
- `-R`: recursive
- `--reference=<file>`: copy perms from another file
- Symbolic: `+x`, `u+r`, `go-w`, `a=rx`

# Examples
- Private key: `chmod 600 ~/.ssh/id_ed25519`
- SSH directory: `chmod 700 ~/.ssh`
- Make a script executable: `chmod +x scripts/foo.sh`
- Reset a tree: `find dir -type f -exec chmod 644 {} +; find dir -type d -exec chmod 755 {} +`
