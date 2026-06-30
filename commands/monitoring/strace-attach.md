---
slug: strace-attach
name: strace -p PID (debug a running process)
family: monitoring
platform: linux
equivalents: dtruss (macos)
references: man strace
---

# Command
```sh
strace -p <pid> -f -e trace=network -o /tmp/strace.out
```

# When to use
A process is hung or misbehaving and you want to see what syscalls it's making. Common: file-IO stalls, network hangs, sleeps.

# When NOT to use
Production at scale — strace is expensive (every syscall is paused). On hot paths it can slow the process dramatically.
Low-level performance work — use `perf` or `bpftrace` instead.

# Gotchas
- `-f` traces forks (child threads/processes). Without it, a forking process disappears from view.
- `-e trace=network` (or `=file`, `=signal`, etc.) filters by syscall category — drastically reduces output noise.
- Strace adds significant overhead — a CPU-bound process may be 10-100x slower while attached.
- Attaching to PID 1 (init) is almost always a bad idea.
- Modern alternative for live observation without slowdown: `bpftrace` or `bcc` tools.

# Flags
- `-p <pid>`: attach to running process
- `-f`: trace forked children
- `-e trace=<category>`: filter syscalls (file, network, signal, process, ipc)
- `-c`: count, don't dump (summary at end)
- `-T`: time spent in each syscall
- `-tt`: timestamp with microseconds
- `-o <file>`: write to file
- `-s <n>`: max string length to print (default 32; increase for full strings)

# Examples
- All syscalls of running process: `sudo strace -p <pid> -f -o /tmp/strace.out`
- Just network: `sudo strace -p <pid> -e trace=network`
- Summary: `sudo strace -p <pid> -c` (Ctrl-C to stop and see summary)
- Where is it stuck: `cat /proc/<pid>/stack; cat /proc/<pid>/wchan` (faster than strace, doesn't pause)
