---
slug: chown-recursive
name: chown -R user:group dir (own a tree)
family: perms
platform: cross-platform
equivalents: 
references: man chown
---

# Command
```sh
chown -R <user>:<group> <path>
```

# When to use
Fix ownership after `sudo`-running something that wrote files as root.

# When NOT to use
On a shared system where you might own files you shouldn't.
Drvfs / Windows mount — chown is a no-op there.

# Gotchas
- `chown -R user:group` changes BOTH owner and group. Omit `:group` to keep group as-is.
- `chown -R user .` follows symlinks by default. Use `-h` to operate on the link itself, not its target. Add `-P` to NEVER follow.
- If you got 'permission denied' on chown, you're not root — wrap in sudo.
- Common after-pip: `sudo chown -R $(whoami) ~/.npm` or `~/.cache/pip` if a sudo install dropped root-owned files.

# Flags
- `-R`: recursive
- `-h`: operate on symlinks themselves (don't follow)
- `--reference=<file>`: copy ownership from another file
- `-c`: report only when a change is made (verbose-but-quiet mode)

# Examples
- Reclaim a dir: `sudo chown -R $(whoami):$(id -gn) /opt/myapp`
- Match another file: `sudo chown --reference=/etc/passwd /etc/myconfig`
- Group only: `chgrp -R wheel /shared` (chgrp is just chown's group-only form)
