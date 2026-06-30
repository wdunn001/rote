---
slug: nohup-disown
name: nohup + disown (background a long process)
family: process
platform: cross-platform
equivalents: systemd-run --user (systemd); tmux / screen (with attach later); pm2 (node)
references: man nohup; man disown
---

# Command
```sh
nohup <cmd> > <logfile> 2>&1 </dev/null &
disown
```

# When to use
Start a long-running command from a shell, then log out without killing it.

# When NOT to use
Production daemons — use systemd / supervisord / a process manager. nohup is for ad-hoc.
Needing to attach back later — use `tmux` or `screen`.

# Gotchas
- WITHOUT `</dev/null`, the process inherits your terminal's stdin and can hang on read attempts.
- WITHOUT `> <log> 2>&1`, output goes to `nohup.out` in the current dir — surprise file.
- `disown` removes the job from the shell's job table so the shell won't send SIGHUP on exit (nohup blocks SIGHUP via the syscall but jobs-table state can still confuse).
- The combination `nohup ... &` + `disown` is belt + suspenders. Either alone usually works; both together always works.

# Flags
nohup: no flags worth knowing — it just sets up the signal handler and execs.

disown:
- `-h`: don't remove from job table, just mark to not receive HUP
- `-a`: all jobs
- `%<n>`: specific job number

# Examples
- Run + detach: `nohup ./long-task.sh > /tmp/long-task.log 2>&1 </dev/null &; disown`
- Server start (rote uses this): `nohup ./server/start.sh >> data/server.log 2>&1 </dev/null &`
- More modern alt: `systemd-run --user --scope --unit=my-task /path/to/task` (gets you cgroup + log isolation)
