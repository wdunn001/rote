---
slug: rsync-avzp
name: rsync -avzP (the canonical sync invocation)
family: fs
platform: cross-platform
equivalents: scp -r (one-shot, no incremental); robocopy (windows)
references: man rsync; https://rsync.samba.org/
---

# Command
```sh
rsync -avzP --delete <src>/ <user>@<host>:<dest>/
```

# When to use
Incremental file sync between two locations — across SSH or locally. The `-a` flag set handles 99% of legit use cases.

# When NOT to use
Need versioning / snapshots — use Restic, borg, btrfs send/receive.
Massive small-file syncs over high-latency links — `rsync` is single-threaded; consider `rclone` with `--transfers N`.

# Gotchas
- TRAILING SLASH ON SOURCE MATTERS. `rsync src/ dest` copies the CONTENTS of src into dest. `rsync src dest` copies src as a SUBDIRECTORY of dest. The classic foot-gun.
- `--delete` removes files at dest that no longer exist at src. With it, src is the source of truth. Without it, dest accumulates stale files.
- `-a` is shorthand for `-rlptgoD` (recursive, links, perms, times, group, owner, devices). Skipping `-a` and forgetting `-t` can leave timestamps wrong, breaking subsequent incremental syncs.
- The themildtake-deploy.sh uses this pattern; see the script for the canonical Acme use.

# Flags
- `-a` / `--archive`: shorthand for -rlptgoD (most common)
- `-v` / `--verbose`: be chatty
- `-z` / `--compress`: compress over the wire
- `-P`: `--partial --progress` (resume + show progress)
- `--delete`: remove files at dest not in src
- `--exclude=<pattern>`: skip matching paths (repeat)
- `--dry-run` / `-n`: show what WOULD happen
- `-e 'ssh -p 2222'`: custom ssh args (e.g. non-22 port)

# Examples
- Deploy via SSH: `rsync -avzP --delete --exclude='.git' ./dist/ user@host:/srv/app/`
- Backup home to USB: `rsync -avzP ~/Documents/ /media/usb/Documents/`
- Dry-run first: `rsync -avzPn --delete src/ dst/`
