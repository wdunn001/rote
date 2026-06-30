---
slug: tmux-basics
name: tmux basics (new / attach / detach)
family: process
platform: cross-platform
equivalents: screen (older, similar); zellij (modern)
references: man tmux
---

# Command
```sh
tmux new -s <name>       # create + attach
tmux attach -t <name>    # reattach
tmux ls                  # list sessions
# Inside: Ctrl-b d = detach; Ctrl-b c = new window; Ctrl-b n/p = next/prev
```

# When to use
Long-running processes you want to leave running on a remote box; multi-pane terminal layouts; collaborative shell sessions.

# When NOT to use
Single short command — use `nohup` + `&`.
Production services — use systemd.

# Gotchas
- The prefix key is `Ctrl-b` by default. Most people remap to `Ctrl-a` (more ergonomic) in `~/.tmux.conf`.
- Detaching is `Ctrl-b d` (NOT `exit`, which kills the shell).
- A session can have many windows (Ctrl-b c to create), and each window many panes (Ctrl-b % to split).
- `tmux kill-session -t <name>` kills the named session and everything in it.
- For sharing a session with another user: `tmux new -s shared` then have them `tmux attach -t shared` (with appropriate perms).

# Flags
- `new -s <name>`: create named session
- `new -d -s <name> <cmd>`: detached start with a command
- `attach -t <name>`: reattach
- `ls`: list sessions
- `kill-session -t <name>` / `kill-server`: cleanup
- `send-keys -t <name>:<window> '<keys>' Enter`: scriptable input

# Examples
- Start: `tmux new -s deploy`
- Detach: `Ctrl-b d`
- Reattach: `tmux attach -t deploy`
- Run a one-off in background: `tmux new -d -s background-job 'sleep 1000; echo done'`
- Script-friendly: `tmux send-keys -t deploy:0 'systemctl restart api' Enter`
