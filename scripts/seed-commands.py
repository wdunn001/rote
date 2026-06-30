#!/usr/bin/env python3
"""
script: seed-commands.py
purpose: Generate the curated initial markdown for the commands catalog —
         canonical console invocations with gotchas + cross-platform
         equivalents.  Idempotent.
family: seed-commands
environment: cross-python
inputs:  --root <path>   default /path/to/rote/
         --dry-run       print what would be written
outputs: per-file lines
exit 0 success, 5 bad args
added: 2026-06-03
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path


COMMANDS: list[dict] = [
    # ============================ package-mgmt ============================
    {
        "slug": "apt-get-install-with-update",
        "name": "apt-get install (with update first)",
        "family": "package-mgmt",
        "platform": "debian, ubuntu, wsl-ubuntu",
        "equivalents": "dnf install (fedora); brew install (macos); choco install (windows); apk add (alpine); pacman -S (arch)",
        "command": "apt-get update && apt-get install -y <package> [<package>...]",
        "when_to_use": "Non-interactive package install in scripts, Dockerfiles, CI.",
        "when_not_to_use": "Interactive shell — use `apt install` (friendlier UI, same backend). You just ran `apt-get update` — skip the chain.",
        "gotchas": "- WITHOUT the `&& apt-get update` you can get stale apt cache: 'package not found' or wrong-version installs.\n- `-y` is essential non-interactively; without it the install hangs on the first confirmation prompt.\n- Use `apt-get` (NOT `apt`) in scripts. `apt` itself warns 'do not use in scripts' because its CLI is unstable.\n- `--no-install-recommends` can drastically cut install size and prevent surprise dependencies.\n- Run as root (or via sudo) — apt-get will refuse otherwise.",
        "flags": "- `-y` / `--yes`: auto-answer yes to all prompts\n- `--no-install-recommends`: skip Recommended deps (smaller install)\n- `--no-install-suggests`: skip Suggested deps\n- `-q` / `--quiet`: less output (use in CI)\n- `--reinstall`: force re-install even if already present\n- `-o Dpkg::Options::=\"--force-confnew\"`: keep new config files on conflict",
        "examples": "- Dockerfile: `RUN apt-get update && apt-get install -y --no-install-recommends curl jq && rm -rf /var/lib/apt/lists/*`\n- One-liner: `sudo apt-get update && sudo apt-get install -y postgresql-client`",
        "references": "man apt-get; https://manpages.debian.org/apt-get",
    },
    {
        "slug": "apt-vs-apt-get",
        "name": "apt vs apt-get (when to pick which)",
        "family": "package-mgmt",
        "platform": "debian, ubuntu",
        "equivalents": "",
        "command": "apt install <pkg>   # interactive shell\napt-get install -y <pkg>  # scripts / CI",
        "when_to_use": "Decide which command-line tool to use for Debian/Ubuntu package operations.",
        "when_not_to_use": "Not a runtime command — this is a reference for picking between two tools.",
        "gotchas": "- `apt` shows progress bars + colored output + an upgradable-packages list at the end. Looks pretty in a terminal; breaks log scrapers.\n- `apt`'s output format is NOT a stable CLI contract — it WILL change between versions.\n- `apt-get`'s output is the stable scripting contract. Use it in scripts.\n- Both call the same backend (libapt); same commands work on both.",
        "flags": "Identical flag set; `apt` is just a friendlier front-end.",
        "examples": "- Day-to-day: `apt search postgres`, `apt show postgresql-client`\n- Scripts: `apt-get install -y postgresql-client`",
        "references": "https://manpages.debian.org/apt",
    },
    {
        "slug": "brew-install",
        "name": "brew install (macOS)",
        "family": "package-mgmt",
        "platform": "macos",
        "equivalents": "apt-get install (debian/ubuntu); dnf install (fedora); choco install (windows); apk add (alpine)",
        "command": "brew install <formula> [<formula>...]",
        "when_to_use": "Install CLI tools and libraries on macOS.",
        "when_not_to_use": "GUI apps — use `brew install --cask <cask>` instead. System Python packages — use pyenv / asdf / nix.",
        "gotchas": "- Homebrew updates ALL formulas during `brew update`; the install command no longer auto-runs update (it used to). Run `brew update` first if you want the latest formula.\n- Bottle (prebuilt) downloads are fast; building from source can be very slow on big formulas (e.g. ffmpeg, gcc).\n- On Apple Silicon, brew installs to `/opt/homebrew`; on Intel, to `/usr/local`. Scripts that hardcode paths break across architectures.",
        "flags": "- `--cask`: GUI/desktop app instead of CLI formula\n- `--HEAD`: build from tip of master (no bottle)\n- `-v` / `--verbose`: show what's happening\n- `--only-dependencies`: install deps but not the formula itself",
        "examples": "- `brew install jq fd ripgrep`\n- `brew install --cask iterm2`",
        "references": "https://docs.brew.sh/",
    },
    {
        "slug": "pip-install-frozen",
        "name": "pip install with requirements.txt",
        "family": "package-mgmt",
        "platform": "cross-platform",
        "equivalents": "npm ci (node); cargo build (rust); bundle install (ruby)",
        "command": "pip install --no-cache-dir -r requirements.txt",
        "when_to_use": "Install pinned Python dependencies in a venv from a requirements file.",
        "when_not_to_use": "Multi-package management with lockfile semantics — use `pip-compile` + `pip-sync`, Poetry, uv, or pdm. Reproducible installs across machines — use `requirements.txt` produced by `pip freeze` or `pip-compile` with HASH pinning.",
        "gotchas": "- `--no-cache-dir` is recommended inside Docker; otherwise the cache stays in the image layer wasting space.\n- pip resolves the FIRST requirement and works downward; conflicting requirements may pick wrong versions silently. Use `pip check` after install.\n- Don't `pip install` system-wide on managed systems (Debian PEP 668 marks them externally-managed — requires `--break-system-packages` or a venv).\n- Use `python -m pip` instead of bare `pip` to avoid PATH ambiguity in scripts.",
        "flags": "- `--no-cache-dir`: don't write/read the cache (Dockerfile-friendly)\n- `--upgrade`: upgrade already-installed packages\n- `--user`: install to user site-packages (no root)\n- `--no-deps`: skip dependency resolution\n- `--target <dir>`: install to a specific directory\n- `-c constraints.txt`: pin versions even if requirements.txt is loose",
        "examples": "- Dockerfile: `RUN pip install --no-cache-dir -r requirements.txt`\n- Local: `python -m pip install --upgrade pip wheel && python -m pip install -r requirements.txt`",
        "references": "https://pip.pypa.io/",
    },
    {
        "slug": "npm-ci-vs-install",
        "name": "npm ci vs npm install",
        "family": "package-mgmt",
        "platform": "cross-platform",
        "equivalents": "yarn install --frozen-lockfile; pnpm install --frozen-lockfile",
        "command": "npm ci   # CI / reproducible\nnpm install   # dev / mutating",
        "when_to_use": "CI, Docker builds, reproducible installs — `npm ci`. Local dev where you ARE changing package.json — `npm install`.",
        "when_not_to_use": "Don't `npm install` in CI: it can mutate package-lock.json silently and the resulting builds aren't reproducible.",
        "gotchas": "- `npm ci` DELETES node_modules and reinstalls clean. Faster than `install` for cold caches because it skips dependency resolution (it trusts the lockfile).\n- `npm ci` REFUSES to run if package.json and package-lock.json are out of sync.\n- Local `npm install` updates the lockfile to whatever it resolved.\n- Always commit package-lock.json. Without it, every install is non-deterministic.",
        "flags": "- `--production` / `--omit=dev`: skip devDependencies (smaller install for prod images)\n- `--ignore-scripts`: skip postinstall scripts (security)\n- `--prefer-offline`: use cache before network",
        "examples": "- Dockerfile: `RUN npm ci --omit=dev`\n- Local: `npm install lodash --save`",
        "references": "https://docs.npmjs.com/cli/v10/commands/npm-ci",
    },

    # ============================ container ============================
    {
        "slug": "docker-compose-up-build",
        "name": "docker compose up -d --build",
        "family": "container",
        "platform": "cross-platform",
        "equivalents": "",
        "command": "docker compose up -d --build [<service>...]",
        "when_to_use": "After changing a Dockerfile or build context — forces image rebuild then brings the stack up detached.",
        "when_not_to_use": "Just a config change with no Dockerfile diff — use `docker compose up -d` (faster, no rebuild).\nProduction with downtime constraints — see the host-direct-rebuild anti-pattern; use the deploy pipeline that recreates the dependent container too (web nginx needs to re-resolve the api IP).",
        "gotchas": "- `--build` rebuilds EVERY service unless you name one. Targeting a single service: `docker compose up -d --build api`.\n- Recreating an api container without restarting the nginx that proxies to it leaves nginx with the stale upstream IP — 502s. See anti-pattern `host-direct-rebuild-bypassing-npm-run-deploy`.\n- For BuildKit DeadlineExceeded under load: prepend `COMPOSE_PARALLEL_LIMIT=1 COMPOSE_BAKE=false` and consider serial build (Acme's `DEPLOY_COMPOSE_BUILD_SERIAL=1`).",
        "flags": "- `-d` / `--detach`: run in background\n- `--build`: rebuild images before starting\n- `--force-recreate`: recreate containers even if config hasn't changed\n- `--no-deps`: don't start linked services\n- `--scale <svc>=N`: scale a service to N replicas\n- `--remove-orphans`: remove services not in the current compose file",
        "examples": "- Full rebuild: `docker compose up -d --build`\n- One service: `docker compose up -d --build api`\n- Force recreate after env change: `docker compose up -d --force-recreate api`",
        "references": "https://docs.docker.com/compose/reference/up/",
    },
    {
        "slug": "docker-exec-interactive",
        "name": "docker exec -it (interactive shell into container)",
        "family": "container",
        "platform": "cross-platform",
        "equivalents": "",
        "command": "docker exec -it <container> bash   # or sh / zsh",
        "when_to_use": "Debugging a running container — inspect filesystem, env vars, processes.",
        "when_not_to_use": "Persistent changes — they're lost on container recreate. Use a volume + edit on the host.\nProduction debugging — exec'ing into prod isn't an audit trail. Use logs + a sidecar pattern.",
        "gotchas": "- `bash` isn't installed in alpine-based images — use `sh`.\n- `-it` (interactive + TTY) is what you want for a shell; `-i` alone for piping data; `-t` alone for log-only.\n- Container must be RUNNING. To debug a crashed container, use `docker logs` or `docker run --rm --entrypoint sh <image>`.",
        "flags": "- `-i`: keep STDIN open\n- `-t`: allocate a pseudo-TTY\n- `-u <user>`: run as specific user (often `-u 0` for root debugging)\n- `-w <dir>`: working directory\n- `-e VAR=value`: env var for this exec session only",
        "examples": "- Root shell into a container: `docker exec -it -u 0 acme-api-1 bash`\n- Run a one-off command: `docker exec acme-postgres-1 psql -U acme -c '\\dt'`",
        "references": "https://docs.docker.com/engine/reference/commandline/exec/",
    },
    {
        "slug": "docker-logs-follow",
        "name": "docker logs --tail N -f",
        "family": "container",
        "platform": "cross-platform",
        "equivalents": "kubectl logs -f --tail=N <pod>",
        "command": "docker logs --tail 100 -f <container>",
        "when_to_use": "Live-tail the last N lines of a container's logs to debug a misbehaving service.",
        "when_not_to_use": "Log analysis at scale — pipe to a log aggregator (Loki, ELK, Splunk). The docker JSON-file driver isn't great at huge logs.",
        "gotchas": "- Default log driver is `json-file`; if you've set `journald`, `docker logs` may return nothing — use `journalctl CONTAINER_NAME=<name>`.\n- `--tail all` shows the entire history; on a long-running container this can be GB.\n- `--since 5m` and `--until 1m` (relative) or `--since 2026-01-15` (absolute) filter time ranges.\n- Use `-t` to prefix each line with the timestamp (handy when correlating across logs).",
        "flags": "- `--tail N`: last N lines\n- `-f` / `--follow`: stream new lines\n- `-t` / `--timestamps`: prefix RFC3339 timestamps\n- `--since <duration|time>`: relative or absolute start\n- `--until <duration|time>`: relative or absolute end\n- `--details`: include extra log driver metadata",
        "examples": "- `docker logs --tail 50 -f acme-api-1`\n- Time window: `docker logs --since 10m --until 1m acme-rabbitmq-1`\n- Timestamps: `docker logs -t --tail 100 acme-api-1 | grep ERROR`",
        "references": "https://docs.docker.com/engine/reference/commandline/logs/",
    },
    {
        "slug": "docker-system-prune",
        "name": "docker system prune (free up disk)",
        "family": "container",
        "platform": "cross-platform",
        "equivalents": "podman system prune",
        "command": "docker system prune -af --volumes",
        "when_to_use": "Reclaim disk space on a dev machine that's accumulated stopped containers, unused images, untagged dangling images, and abandoned volumes.",
        "when_not_to_use": "Production — almost certainly deletes things you care about. Run with smaller subcommands (`docker image prune`, `docker container prune`) and read the prompt first.",
        "gotchas": "- `-a` removes ALL unused images (not just dangling) — VERY aggressive.\n- `--volumes` removes anonymous volumes too. If you have data in a volume but no running container is attached, it's gone.\n- Always inspect first with `docker system df` to see what's eating space.\n- Per-resource variants are safer: `docker image prune -a`, `docker container prune`, `docker volume prune` (NEVER `--volumes` on prod).",
        "flags": "- `-a` / `--all`: include unused images (not just dangling)\n- `--volumes`: also remove volumes\n- `-f` / `--force`: skip confirmation\n- `--filter \"until=24h\"`: only resources older than 24h",
        "examples": "- Inspect first: `docker system df`\n- Conservative: `docker system prune` (containers + dangling images + networks; no volumes)\n- Aggressive (dev box): `docker system prune -af --volumes`\n- Only old: `docker image prune -a --filter \"until=168h\"`",
        "references": "https://docs.docker.com/engine/reference/commandline/system_prune/",
    },
    {
        "slug": "docker-inspect-format",
        "name": "docker inspect with --format",
        "family": "container",
        "platform": "cross-platform",
        "equivalents": "",
        "command": "docker inspect --format '{{.State.Status}} {{.State.Health.Status}}' <container>",
        "when_to_use": "Scripted introspection of container state — health status, IPs, mounts, env vars.",
        "when_not_to_use": "Quick human-readable look — just `docker inspect` and read the JSON.",
        "gotchas": "- The Go template language is the format DSL. `{{.State.Health.Status}}` returns `<no value>` (literally) when the container has no HEALTHCHECK — handle that case in your script.\n- `.HostConfig.PortBindings`, `.NetworkSettings.Networks`, `.Mounts` are the most useful subtrees.\n- `docker inspect` accepts container OR image as the arg; same template DSL.",
        "flags": "- `--format <template>` / `-f`: Go template; emit specific fields\n- `--size`: include disk usage info (containers)\n- `--type container|image|volume|network`: explicit type",
        "examples": "- Container IP: `docker inspect -f '{{.NetworkSettings.IPAddress}}' <c>`\n- All env vars: `docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' <c>`\n- Bind mounts: `docker inspect -f '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}' <c>`\n- Image SHA: `docker inspect -f '{{.Image}}' <c>`",
        "references": "https://docs.docker.com/engine/reference/commandline/inspect/",
    },

    # ============================ git ============================
    {
        "slug": "git-rebase-interactive",
        "name": "git rebase -i HEAD~N (interactive rebase)",
        "family": "git",
        "platform": "cross-platform",
        "equivalents": "jj edit (jujutsu)",
        "command": "git rebase -i HEAD~<N>",
        "when_to_use": "Squash, reorder, edit, or drop the last N commits before pushing. Clean up a feature branch's history for a PR.",
        "when_not_to_use": "Commits already pushed to a shared branch — you'll force-push and rewrite history other people depend on. ONLY use on personal branches before pushing.\nMore than ~20 commits — interactive rebase becomes unwieldy. Use `git filter-repo` or `git rebase --autosquash` for systematic operations.",
        "gotchas": "- The editor opens with the COMMITS BUT THE ORDER IS REVERSED FROM `git log`. Top of the file = oldest commit; bottom = newest.\n- `pick`, `reword`, `edit`, `squash`, `fixup`, `drop`, `exec`. Most-used: `squash` and `fixup`.\n- `squash` keeps the commit message; `fixup` discards it (use when the original message was junk like 'fix typo').\n- If you mess up: `git reflog` shows every HEAD change; `git reset --hard HEAD@{<N>}` restores.\n- `--autosquash` + `--autostash` are quality-of-life: autosquash if your commits are tagged `fixup!` / `squash!`; autostash for uncommitted changes.",
        "flags": "- `-i` / `--interactive`: open editor (the whole point)\n- `--autosquash`: auto-mark `fixup!` / `squash!` commits\n- `--autostash`: stash working tree before, restore after\n- `--continue` / `--abort` / `--skip`: control flow after a conflict\n- `--onto <newbase>`: change WHAT we're rebasing onto (advanced)",
        "examples": "- Squash last 3 commits into one: `git rebase -i HEAD~3`, change all but the first to `squash`.\n- Drop a bad commit: `git rebase -i HEAD~5`, change line to `drop`.\n- Edit a commit's message 4 back: `git rebase -i HEAD~4`, change line to `reword`.",
        "references": "https://git-scm.com/docs/git-rebase",
    },
    {
        "slug": "git-reflog-recovery",
        "name": "git reflog (recover from mistakes)",
        "family": "git",
        "platform": "cross-platform",
        "equivalents": "jj op log (jujutsu)",
        "command": "git reflog",
        "when_to_use": "You did something destructive (hard reset, force-checkout, bad rebase, accidentally deleted a branch) and want to recover.",
        "when_not_to_use": "The repo has been garbage-collected (rare; default GC keeps reflog 30-90 days). For long-term recovery, you need backups.\nYou just want to see commits — use `git log` instead.",
        "gotchas": "- Reflog tracks HEAD movements LOCALLY only. Pushes / pulls record entries; remote operations on OTHER machines don't.\n- After ~30 days (gc.reflogExpire default 90), reflog entries can be GC'd.\n- Each ref has its own reflog: `git reflog show <branchname>`.\n- `HEAD@{N}` references the Nth-most-recent HEAD position.",
        "flags": "- `show <ref>`: see the reflog for a specific ref (default HEAD)\n- `--date=iso`: show timestamps in ISO format (easier to scan)\n- `expire`: prune old entries (rarely needed)\n- `delete <ref>@{N}`: remove a single entry",
        "examples": "- See your recent HEAD movements: `git reflog`\n- Recover a lost commit: `git reflog`, find the SHA, then `git cherry-pick <sha>` or `git branch recover-<topic> <sha>`\n- Restore after bad reset: `git reset --hard HEAD@{1}` (go back ONE HEAD movement)",
        "references": "https://git-scm.com/docs/git-reflog",
    },
    {
        "slug": "git-log-graph",
        "name": "git log --oneline --graph --all",
        "family": "git",
        "platform": "cross-platform",
        "equivalents": "tig (TUI); gitk (Tk GUI)",
        "command": "git log --oneline --graph --all --decorate",
        "when_to_use": "Visualize branch structure + recent commits across all refs in one screen.",
        "when_not_to_use": "Repo with 10k+ commits and 100+ branches — output gets unreadable. Filter by --since / --author / --grep.",
        "gotchas": "- `--all` shows ALL refs including stashes and remote-tracking branches. Drop it for current branch only.\n- Alias this. Most devs set `git lg` to this exact command in `~/.gitconfig`.\n- The graph shows the topology truthfully; what you THINK happened may not be what did.",
        "flags": "- `--oneline`: one line per commit (SHA + message)\n- `--graph`: ASCII branch topology\n- `--all`: every ref\n- `--decorate`: show ref names next to SHAs\n- `--since=2w`: limit to last 2 weeks\n- `--author=<pattern>`: filter by author\n- `-N` (e.g. `-30`): show only the N most recent commits",
        "examples": "- Set as alias: `git config --global alias.lg 'log --oneline --graph --all --decorate'` then `git lg`\n- Last 50 commits: `git log --oneline --graph --all -50`\n- This branch only: `git log --oneline --graph -30`",
        "references": "https://git-scm.com/docs/git-log",
    },
    {
        "slug": "git-bisect",
        "name": "git bisect (find the commit that broke things)",
        "family": "git",
        "platform": "cross-platform",
        "equivalents": "",
        "command": "git bisect start <bad-commit> <good-commit>\n# (test current commit, then) git bisect good   OR   git bisect bad\n# ... repeat ...\ngit bisect reset",
        "when_to_use": "A regression appeared and you don't know which commit caused it. Binary search through history with O(log N) test runs.",
        "when_not_to_use": "The regression is intermittent (bisect needs a reliable test). The commit space has merge commits with broken trees in between (bisect handles this but the noise can confuse).",
        "gotchas": "- ALWAYS `git bisect reset` when done — otherwise HEAD is stuck mid-bisect.\n- Bisect tries the midpoint, not the average; on a non-linear history with merges this can land on a 'merge commit that doesn't compile' even though no actual code introduced the bug.\n- Automate the test: `git bisect run <script>` exits 0 for good, non-zero for bad. The script runs your test on each candidate.",
        "flags": "- `start <bad> <good>`: kick off\n- `good` / `bad`: classify the current candidate\n- `skip`: this candidate can't be tested (don't classify)\n- `run <command>`: automate — script's exit code classifies\n- `reset`: stop and return to HEAD",
        "examples": "- Manual: `git bisect start HEAD HEAD~50`, then for each step test the app and run `git bisect good` or `git bisect bad`.\n- Automated: `git bisect run npm test` — bisect runs `npm test` on each candidate.",
        "references": "https://git-scm.com/docs/git-bisect",
    },
    {
        "slug": "git-worktree",
        "name": "git worktree add (parallel checkouts)",
        "family": "git",
        "platform": "cross-platform",
        "equivalents": "",
        "command": "git worktree add ../<dir> <branch>",
        "when_to_use": "Work on two branches simultaneously without `git stash` or duplicate clones. Each worktree has its own working dir; they share the .git directory.",
        "when_not_to_use": "Working on the same branch in two worktrees (git refuses by default; for good reason).\nLong-term — worktrees can be forgotten and leak state. Use `git worktree list` + `git worktree remove` regularly.",
        "gotchas": "- Worktrees share refs but NOT the working directory. Changes in one don't affect another.\n- `git worktree remove` cleans up; manual `rm -rf` leaves the .git/worktrees/<name> directory dangling (use `git worktree prune` to clean).\n- When the worktree branch is later merged + deleted, the worktree dir doesn't auto-clean. Remove it.\n- Some Acme sessions create worktrees during agent fan-out (e.g. C3 work) — list them periodically.",
        "flags": "- `add <path> <branch>`: create\n- `add -b <new-branch> <path>`: create a new branch in this worktree\n- `list`: show all worktrees\n- `remove <path>`: clean up\n- `prune`: remove records of vanished worktrees\n- `lock`: prevent removal (for long-running offline worktrees)",
        "examples": "- Bug-fix on a separate dir: `git worktree add ../myapp-hotfix hotfix/critical-bug`\n- Look at the topology: `git worktree list`\n- Clean up: `git worktree remove ../myapp-hotfix`",
        "references": "https://git-scm.com/docs/git-worktree",
    },
    {
        "slug": "git-restore",
        "name": "git restore (modern unstage + revert)",
        "family": "git",
        "platform": "cross-platform",
        "equivalents": "git reset HEAD <file>; git checkout -- <file>  (the deprecated forms)",
        "command": "git restore --staged <file>   # unstage\ngit restore <file>            # discard working-tree changes",
        "when_to_use": "Unstage a file you accidentally `git add`'d. Or discard uncommitted changes in working dir.",
        "when_not_to_use": "Already-pushed changes — use `git revert <sha>` (creates an inverse commit).\nStashed changes — `git stash` and friends (which we DON'T use; see `git-stash` anti-pattern — use WIP commits instead).",
        "gotchas": "- `git restore <file>` IS DESTRUCTIVE — your uncommitted changes in that file are gone. No reflog, no recovery.\n- `git restore --staged <file>` only unstages; the working dir copy is untouched.\n- Without `--staged` or `--worktree`, defaults to `--worktree` (i.e. destroys uncommitted changes).\n- For 'undo last commit but keep changes': `git reset --soft HEAD~1`. Not `git restore`.",
        "flags": "- `--staged`: unstage\n- `--worktree`: discard working-tree changes (default)\n- `--source=<commit>`: restore from a specific commit instead of HEAD\n- `-p` / `--patch`: interactive hunk selection",
        "examples": "- Unstage one file: `git restore --staged src/index.ts`\n- Discard local changes: `git restore src/index.ts` (DESTRUCTIVE)\n- Restore old version: `git restore --source=HEAD~3 src/index.ts`",
        "references": "https://git-scm.com/docs/git-restore",
    },

    # ============================ fs ============================
    {
        "slug": "rsync-avzp",
        "name": "rsync -avzP (the canonical sync invocation)",
        "family": "fs",
        "platform": "cross-platform",
        "equivalents": "scp -r (one-shot, no incremental); robocopy (windows)",
        "command": "rsync -avzP --delete <src>/ <user>@<host>:<dest>/",
        "when_to_use": "Incremental file sync between two locations — across SSH or locally. The `-a` flag set handles 99% of legit use cases.",
        "when_not_to_use": "Need versioning / snapshots — use Restic, borg, btrfs send/receive.\nMassive small-file syncs over high-latency links — `rsync` is single-threaded; consider `rclone` with `--transfers N`.",
        "gotchas": "- TRAILING SLASH ON SOURCE MATTERS. `rsync src/ dest` copies the CONTENTS of src into dest. `rsync src dest` copies src as a SUBDIRECTORY of dest. The classic foot-gun.\n- `--delete` removes files at dest that no longer exist at src. With it, src is the source of truth. Without it, dest accumulates stale files.\n- `-a` is shorthand for `-rlptgoD` (recursive, links, perms, times, group, owner, devices). Skipping `-a` and forgetting `-t` can leave timestamps wrong, breaking subsequent incremental syncs.\n- The themildtake-deploy.sh uses this pattern; see the script for the canonical Acme use.",
        "flags": "- `-a` / `--archive`: shorthand for -rlptgoD (most common)\n- `-v` / `--verbose`: be chatty\n- `-z` / `--compress`: compress over the wire\n- `-P`: `--partial --progress` (resume + show progress)\n- `--delete`: remove files at dest not in src\n- `--exclude=<pattern>`: skip matching paths (repeat)\n- `--dry-run` / `-n`: show what WOULD happen\n- `-e 'ssh -p 2222'`: custom ssh args (e.g. non-22 port)",
        "examples": "- Deploy via SSH: `rsync -avzP --delete --exclude='.git' ./dist/ user@host:/srv/app/`\n- Backup home to USB: `rsync -avzP ~/Documents/ /media/usb/Documents/`\n- Dry-run first: `rsync -avzPn --delete src/ dst/`",
        "references": "man rsync; https://rsync.samba.org/",
    },
    {
        "slug": "find-exec-plus",
        "name": "find . -name <pattern> -exec <cmd> {} +",
        "family": "fs",
        "platform": "cross-platform",
        "equivalents": "fd <pattern> -x <cmd> (rust replacement, much faster)",
        "command": "find . -type f -name '<pattern>' -exec <cmd> {} +",
        "when_to_use": "Run a command across many matched files efficiently. Pipeline alternative is `xargs`.",
        "when_not_to_use": "Simple grep — use `grep -rE` directly.\nVery fast matching — use `fd` (rust-based, respects .gitignore, much faster).\nFiles you want to delete — use `-delete` instead of `-exec rm` (faster and safer).",
        "gotchas": "- `{} +` (with plus) batches matches into ONE `<cmd>` invocation per batch — much faster than `{} \\;` which forks a process per file.\n- `\\;` forks a process per file. Use only when the command can take exactly one arg.\n- `-name` is case-sensitive; `-iname` for case-insensitive.\n- Watch quoting: `find . -name '*.txt'` (quoted) vs `find . -name *.txt` (shell expands glob first — often wrong).\n- For binary-vs-text decisions, pipe to grep -I.",
        "flags": "- `-type f|d|l`: file / dir / symlink\n- `-name <glob>` / `-iname` (case-insens)\n- `-exec <cmd> {} +`: batched exec\n- `-exec <cmd> {} \\;`: one exec per file\n- `-delete`: built-in delete (no process fork)\n- `-mtime -7`: modified in last 7 days (`-mmin -10` for minutes)\n- `-size +100M`: files larger than 100 MB\n- `-not <test>`: invert",
        "examples": "- Touch all .py: `find . -type f -name '*.py' -exec touch {} +`\n- Delete .pyc: `find . -name '*.pyc' -delete`\n- Big files: `find . -type f -size +100M`\n- Recently changed: `find . -type f -mtime -1`\n- Grep across matched files: `find . -name '*.ts' -exec grep -l 'TODO' {} +`",
        "references": "man find",
    },
    {
        "slug": "tar-extract",
        "name": "tar extract (xzf / xJf / xjf)",
        "family": "fs",
        "platform": "cross-platform",
        "equivalents": "unzip (for .zip); 7z x (universal)",
        "command": "tar xzf <file>.tar.gz     # gzip\ntar xJf <file>.tar.xz     # xz\ntar xjf <file>.tar.bz2    # bzip2\ntar xf  <file>.tar.zst    # zstd (modern tar auto-detects)",
        "when_to_use": "Extract a tarball. Modern GNU tar auto-detects compression with `xf` alone — older systems need the flag.",
        "when_not_to_use": "Archive contains unknown / untrusted content — extract to a sandbox dir first.",
        "gotchas": "- `tar xzf` extracts INTO THE CURRENT DIR. Use `-C <dir>` to target somewhere else.\n- `-v` prints every file — slow on huge archives. Drop it.\n- The TAR-BOMB problem: an archive that extracts to the current dir instead of a subdir, scattering files everywhere. Always `tar tzf <file> | head` first to inspect.\n- Modern tar (GNU 1.30+, macOS bsdtar) auto-detects compression. `tar xf` works for .tar.gz, .tar.xz, .tar.bz2, .tar.zst.",
        "flags": "- `x` extract / `c` create / `t` list\n- `f <file>`: archive file (must be last in flag clump)\n- `z` gzip / `J` xz / `j` bzip2 / no-flag = auto-detect (modern)\n- `v` verbose (slow on big archives)\n- `-C <dir>`: change to dir before operating",
        "examples": "- List first: `tar tzf archive.tar.gz | head`\n- Extract to dir: `tar xzf archive.tar.gz -C /tmp/extracted/`\n- Auto-detect: `tar xf archive.tar.zst` (modern tar handles it)\n- Create: `tar czf archive.tar.gz dir/`",
        "references": "man tar",
    },
    {
        "slug": "du-sh-vs-ncdu",
        "name": "du -sh / ncdu (disk-usage analysis)",
        "family": "fs",
        "platform": "cross-platform",
        "equivalents": "WinDirStat (Windows); GrandPerspective (macOS)",
        "command": "du -sh ./*          # quick per-toplevel\nncdu -x /         # interactive TUI",
        "when_to_use": "Find what's eating disk space. `du -sh` for a quick scan; `ncdu` for interactive drill-down.",
        "when_not_to_use": "Watching disk in real-time — `iotop`, `iostat`. \nDocker disk — `docker system df`.",
        "gotchas": "- `du -sh ./*` skips dotfiles. Use `du -sh ./* ./.*` to include them, OR `du -sh .[!.]* *` to include dotfiles but not `.` and `..`.\n- `du` counts BLOCK USAGE, not byte size. On filesystems with large block sizes, small files appear bigger.\n- `du -h` is human-readable; for sorting use `du -sb` (bytes) and `sort -n`.\n- `ncdu -x` stays on one filesystem (won't cross mount points — important on root).\n- For very large filesystems, `ncdu` can be slow to scan; consider `--exclude` patterns.",
        "flags": "du:\n- `-s`: summary (just the total)\n- `-h`: human-readable (K/M/G)\n- `-x`: one filesystem only\n- `--max-depth=N`\n\nncdu:\n- `-x`: one filesystem\n- `--exclude <pattern>`: skip\n- `-o <file>`: dump scan to file (offline analysis)",
        "examples": "- Per-toplevel: `du -sh ./* | sort -h`\n- Including dotfiles: `du -sh .[!.]* * | sort -h`\n- Interactive drill: `ncdu -x /`\n- Save then view: `ncdu -o /tmp/scan.json /var; ncdu -f /tmp/scan.json`",
        "references": "man du; https://dev.yorhel.nl/ncdu",
    },
    {
        "slug": "lsof-port",
        "name": "lsof -i :PORT (what's listening on a port)",
        "family": "fs",
        "platform": "cross-platform",
        "equivalents": "ss -tlnp; netstat -tlnp (deprecated)",
        "command": "lsof -i :<port>           # processes using this TCP/UDP port\nlsof -i :<port> -sTCP:LISTEN  # just listeners",
        "when_to_use": "'Port 5572 is already in use' — find what's bound. Debug 'why can't I connect to X'.",
        "when_not_to_use": "Production at scale — use `ss` (faster, kernel-native). `lsof` enumerates ALL open files first.",
        "gotchas": "- Without root, `lsof` only shows YOUR processes. Use `sudo lsof -i :PORT` for system-wide.\n- `lsof -i :PORT` returns BOTH listeners and connections to that port. Use `-sTCP:LISTEN` to filter to just listeners.\n- On macOS / WSL, the docker-internal-port might not show via lsof — use `docker ps` for those.",
        "flags": "- `-i :PORT`: by network port\n- `-i TCP` / `-i UDP`: protocol\n- `-i 4` / `-i 6`: IPv4 / IPv6\n- `-n`: don't resolve IPs to hostnames (faster)\n- `-P`: don't translate port numbers to names\n- `-sTCP:LISTEN`: TCP state filter\n- `+c0`: full command names (otherwise truncated to 9)",
        "examples": "- What's on 5572: `sudo lsof -i :5572 -nP`\n- All listeners: `sudo lsof -i -sTCP:LISTEN -nP`\n- A specific process's network: `lsof -i -a -p <pid>`",
        "references": "man lsof",
    },

    # ============================ net-ssh ============================
    {
        "slug": "ssh-tunnel-local",
        "name": "ssh -L (local port forward)",
        "family": "net-ssh",
        "platform": "cross-platform",
        "equivalents": "",
        "command": "ssh -L <local-port>:<remote-host>:<remote-port> <user>@<gateway>",
        "when_to_use": "Reach a service on the SSH server's network from your local machine. Connect to a remote DB from local psql; expose a edge-host service to a local browser; reach a service behind a corporate jumpbox.",
        "when_not_to_use": "You want OTHERS to reach a service on your machine — use `-R` (remote forward) instead.\nProduction proxying — use a real load balancer / proxy / VPN.",
        "gotchas": "- The tunnel is gone when the SSH session ends. For long-running, use `autossh` or `systemd-as-a-service`.\n- `<remote-host>` is resolved on the SSH SERVER's network, not yours. `localhost` means 'localhost from the server's view'.\n- Local port < 1024 needs root.\n- `-N` (no command) + `-f` (background) makes a daemon tunnel without spawning a shell: `ssh -fN -L 5432:localhost:5432 user@host`.",
        "flags": "- `-L <lport>:<host>:<rport>`: local forward\n- `-R <rport>:<host>:<lport>`: remote forward (server-side listen)\n- `-D <port>`: dynamic SOCKS proxy\n- `-N`: don't execute a remote command\n- `-f`: background after auth\n- `-T`: no PTY\n- `-o ServerAliveInterval=60`: send keepalives (avoid corporate idle-kill)",
        "examples": "- Postgres on edge-host accessible locally: `ssh -fN -L 5432:localhost:5432 user@edge-host` then `psql -h localhost -p 5432`\n- MetaMCP browser-reachable from this box: `ssh -fN -L 12008:localhost:12008 user@edge-host` then open http://localhost:12008/\n- Tunnel through jumpbox to internal host: `ssh -L 8443:internal.host:443 user@jumpbox`",
        "references": "man ssh",
    },
    {
        "slug": "ssh-copy-id",
        "name": "ssh-copy-id (install your key)",
        "family": "net-ssh",
        "platform": "cross-platform",
        "equivalents": "",
        "command": "ssh-copy-id [-i ~/.ssh/<key>.pub] <user>@<host>",
        "when_to_use": "First-time setup of password-less SSH to a new host.",
        "when_not_to_use": "Host has password auth disabled — you need an alternative way to land the key (console, infra-as-code, snapshot, etc.).",
        "gotchas": "- The first time, you'll be prompted for the password (that's the point — it uses password auth to install the key, then future logins use the key).\n- Picks the default key (`~/.ssh/id_rsa.pub` or `id_ed25519.pub`). Use `-i` to be explicit.\n- Idempotent — re-running won't duplicate entries.\n- If your shell on the remote is weird (no bash, custom prompt), `ssh-copy-id` may fail silently. Manually: `cat ~/.ssh/id_ed25519.pub | ssh user@host 'cat >> ~/.ssh/authorized_keys'`.",
        "flags": "- `-i <key.pub>`: specific public key\n- `-p <port>`: non-22 SSH port\n- `-o <ssh-opt>`: pass-through SSH options\n- `-n`: dry-run (show what would be installed)",
        "examples": "- Standard: `ssh-copy-id user@edge-host`\n- Specific key: `ssh-copy-id -i ~/.ssh/work_ed25519.pub work@host`\n- Manual fallback: `cat ~/.ssh/id_ed25519.pub | ssh user@host 'mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'`",
        "references": "man ssh-copy-id",
    },
    {
        "slug": "ssh-keygen-ed25519",
        "name": "ssh-keygen -t ed25519 (modern key)",
        "family": "net-ssh",
        "platform": "cross-platform",
        "equivalents": "",
        "command": "ssh-keygen -t ed25519 -C '<email-or-label>'",
        "when_to_use": "Generating a new SSH keypair. Default to ed25519 — small, fast, secure.",
        "when_not_to_use": "Target system doesn't support ed25519 (very old OpenSSH < 6.5). Fall back to `-t rsa -b 4096`.",
        "gotchas": "- USE A PASSPHRASE. Without one, anyone with the file owns the key.\n- Default output: `~/.ssh/id_ed25519` (private) + `~/.ssh/id_ed25519.pub` (public). Don't share the private file.\n- The `-C` comment is just a label — typically your email or 'work-laptop'. Helps you identify keys later.\n- For automation (CI keys), use a SEPARATE key with no passphrase, install it via secrets management, and restrict it via `authorized_keys` options (`command=...`, `restrict`).",
        "flags": "- `-t ed25519|rsa|ecdsa`: algorithm\n- `-b <bits>`: key size (for RSA: 4096)\n- `-C <comment>`: human label\n- `-f <path>`: output path (default ~/.ssh/id_<type>)\n- `-N <passphrase>`: passphrase non-interactively (CAREFUL — visible in shell history)\n- `-a <rounds>`: KDF rounds (more = slower to brute-force)",
        "examples": "- Standard: `ssh-keygen -t ed25519 -C 'wdunn001@gmail.com'`\n- RSA fallback for old systems: `ssh-keygen -t rsa -b 4096 -C 'legacy-vps'`\n- Named: `ssh-keygen -t ed25519 -f ~/.ssh/work_github -C 'work-github-deploy'`",
        "references": "man ssh-keygen",
    },
    {
        "slug": "curl-fssL",
        "name": "curl -fsSL (the script-friendly curl)",
        "family": "net-ssh",
        "platform": "cross-platform",
        "equivalents": "wget -qO-",
        "command": "curl -fsSL <url>",
        "when_to_use": "Fetch content from a URL in a script. The `-fsSL` flag set is what you almost always want.",
        "when_not_to_use": "Need progress display for a human — drop `-s`. Want interactive auth prompts — that's `-u`.",
        "gotchas": "- `-f`: fail on HTTP 4xx/5xx (otherwise curl exits 0 even on a 500). WITHOUT this, your script silently succeeds on broken downloads.\n- `-s`: silent (no progress/error meter). With ONLY `-s`, errors are silent — that's why we add `-S` (show errors despite -s).\n- `-L`: follow redirects. Without it, a 301 returns the redirect HTML, not the target.\n- For piping into shell (`curl ... | sh`) — DON'T. Inspect first. If you must, at minimum verify with a checksum.",
        "flags": "- `-f` / `--fail`: non-zero exit on HTTP error\n- `-s` / `--silent`: no progress meter\n- `-S` / `--show-error`: show errors despite -s\n- `-L` / `--location`: follow redirects\n- `-o <file>` / `--output`: save to file\n- `-O`: save to filename from URL\n- `-m <sec>` / `--max-time`: total timeout\n- `--connect-timeout <sec>`: TCP-establish timeout\n- `-H 'Header: value'`: custom header\n- `-d '<body>'`: POST body\n- `-X POST|PUT|...`: explicit method\n- `-u user:pass`: HTTP basic auth",
        "examples": "- Healthcheck: `curl -fsS -m 5 http://localhost:5572/healthz`\n- POST JSON: `curl -fsS -X POST -H 'Content-Type: application/json' -d '{\"k\":1}' http://api/v1/foo`\n- Download to disk: `curl -fsSLO https://example.com/file.tar.gz`\n- With timeout + retry-ish: `curl -fsSL --max-time 30 --connect-timeout 5 <url>`",
        "references": "man curl",
    },

    # ============================ perms ============================
    {
        "slug": "chmod-common-modes",
        "name": "chmod common modes (600, 644, 700, 755)",
        "family": "perms",
        "platform": "cross-platform",
        "equivalents": "icacls (windows); chmod is also on macOS/BSD with minor differences",
        "command": "chmod 600 <file>   # owner rw, others nothing — secrets/keys\nchmod 644 <file>   # owner rw, world read — docs/configs\nchmod 700 <dir>    # owner rwx, others nothing — ~/.ssh\nchmod 755 <file>   # owner rwx, world rx — scripts/binaries",
        "when_to_use": "Set Unix file permissions. The four common modes cover ~95% of needs.",
        "when_not_to_use": "ACL-based perms (`setfacl`); SELinux labels; Windows ACLs (`icacls`).\nWSL on drvfs (`/mnt/[a-z]/`) — `chmod` is a no-op there. See anti-pattern `silent-chmod-noop-on-drvfs`.",
        "gotchas": "- `chmod 0777` on a secrets file is a recurring security mistake. The user's `deploy.env` was 0777; see the perms remediation in the acme docs.\n- `chmod -R` is RECURSIVE. Use carefully — chmod 600 on a tree breaks every dir's traversal (dirs need x to enter).\n- `find . -type f -exec chmod 644 {} +` then `find . -type d -exec chmod 755 {} +` is the safe way to reset perms across a tree.\n- WSL drvfs ignores chmod. The file mode reports as 0777 always. You need Windows ACLs or `/etc/wsl.conf` metadata.",
        "flags": "- `-R`: recursive\n- `--reference=<file>`: copy perms from another file\n- Symbolic: `+x`, `u+r`, `go-w`, `a=rx`",
        "examples": "- Private key: `chmod 600 ~/.ssh/id_ed25519`\n- SSH directory: `chmod 700 ~/.ssh`\n- Make a script executable: `chmod +x scripts/foo.sh`\n- Reset a tree: `find dir -type f -exec chmod 644 {} +; find dir -type d -exec chmod 755 {} +`",
        "references": "man chmod",
    },
    {
        "slug": "chown-recursive",
        "name": "chown -R user:group dir (own a tree)",
        "family": "perms",
        "platform": "cross-platform",
        "equivalents": "",
        "command": "chown -R <user>:<group> <path>",
        "when_to_use": "Fix ownership after `sudo`-running something that wrote files as root.",
        "when_not_to_use": "On a shared system where you might own files you shouldn't.\nDrvfs / Windows mount — chown is a no-op there.",
        "gotchas": "- `chown -R user:group` changes BOTH owner and group. Omit `:group` to keep group as-is.\n- `chown -R user .` follows symlinks by default. Use `-h` to operate on the link itself, not its target. Add `-P` to NEVER follow.\n- If you got 'permission denied' on chown, you're not root — wrap in sudo.\n- Common after-pip: `sudo chown -R $(whoami) ~/.npm` or `~/.cache/pip` if a sudo install dropped root-owned files.",
        "flags": "- `-R`: recursive\n- `-h`: operate on symlinks themselves (don't follow)\n- `--reference=<file>`: copy ownership from another file\n- `-c`: report only when a change is made (verbose-but-quiet mode)",
        "examples": "- Reclaim a dir: `sudo chown -R $(whoami):$(id -gn) /opt/myapp`\n- Match another file: `sudo chown --reference=/etc/passwd /etc/myconfig`\n- Group only: `chgrp -R wheel /shared` (chgrp is just chown's group-only form)",
        "references": "man chown",
    },

    # ============================ systemd ============================
    {
        "slug": "systemctl-restart",
        "name": "systemctl restart / status / enable",
        "family": "systemd",
        "platform": "debian, ubuntu, fedora, arch",
        "equivalents": "service <name> restart (sysv-init, deprecated); launchctl (macos); sc.exe (windows)",
        "command": "systemctl status <unit>\nsystemctl restart <unit>\nsystemctl enable --now <unit>   # enable at boot AND start now\nsystemctl daemon-reload          # after editing a unit file",
        "when_to_use": "Manage systemd services on a Linux host (the vast majority of modern distros).",
        "when_not_to_use": "Container-runtime processes — docker/podman manage those.\nUser-session services — use `systemctl --user <verb>`.",
        "gotchas": "- After editing a unit file at `/etc/systemd/system/<unit>.service`, you MUST `systemctl daemon-reload` before `restart`, otherwise the old definition is still loaded.\n- `enable` makes it start at boot; `start` makes it run now. `enable --now` does both.\n- `restart` is NOT a graceful reload — it kills + restarts. For nginx-style reload: `systemctl reload <unit>` (only if the unit defines ExecReload).\n- `journalctl -u <unit> -f` is the standard way to follow a service's logs.",
        "flags": "- `start` / `stop` / `restart` / `reload`\n- `enable` / `disable`: boot-time auto-start\n- `enable --now`: enable + start in one\n- `status`: current state + last log lines\n- `daemon-reload`: re-read unit files after edits\n- `--user`: operate on user-scope unit\n- `list-units --type=service --state=running`: enumerate running services",
        "examples": "- Restart api: `sudo systemctl restart acme-api`\n- Enable + start: `sudo systemctl enable --now acme-api`\n- Inspect: `sudo systemctl status acme-api`\n- After unit edit: `sudo systemctl daemon-reload && sudo systemctl restart acme-api`",
        "references": "man systemctl",
    },
    {
        "slug": "journalctl-follow",
        "name": "journalctl -u SERVICE -f (live tail systemd logs)",
        "family": "systemd",
        "platform": "debian, ubuntu, fedora, arch",
        "equivalents": "tail -f /var/log/<service>.log (legacy); docker logs -f (containers)",
        "command": "journalctl -u <unit> -f --since '5m ago'",
        "when_to_use": "Tail / search logs of a systemd-managed service. Replaces tailing `/var/log/<unit>.log`.",
        "when_not_to_use": "Containers — those use the docker log driver. Get them via `docker logs` or the configured driver's destination.\nApplication-level structured logs you want to grep semantically — pipe through `jq` for JSON or use Loki/ELK.",
        "gotchas": "- Without `-u`, you see EVERYTHING. Always scope.\n- `--since` and `--until` accept relative (`5m ago`, `2 days ago`) or absolute (`2026-01-15`) times.\n- `journalctl` paginates with `less` by default. For piping, add `--no-pager` or `| cat`.\n- High-volume services can produce GB of logs; journald defaults to a size cap (`SystemMaxUse` in journald.conf). Old logs vanish silently if not configured.",
        "flags": "- `-u <unit>`: scope to a service\n- `-f`: follow\n- `--since <time>`: from when\n- `--until <time>`: until when\n- `-n N`: last N lines (default `-n 10`)\n- `-p err|warning|info|debug`: priority filter\n- `-o json|json-pretty|short-iso|cat`: output format\n- `-k`: kernel messages only\n- `--no-pager`: don't run through less",
        "examples": "- Live tail: `journalctl -u acme-api -f`\n- Last hour, errors only: `journalctl -u acme-api --since '1h ago' -p err`\n- JSON for grepping: `journalctl -u acme-api -o json --no-pager | jq 'select(.PRIORITY <= \"3\")'`",
        "references": "man journalctl",
    },

    # ============================ monitoring ============================
    {
        "slug": "ps-aux-grep",
        "name": "ps aux | grep <pattern>",
        "family": "monitoring",
        "platform": "cross-platform",
        "equivalents": "pgrep -af <pattern> (cleaner output); top / htop (interactive)",
        "command": "ps aux | grep -v grep | grep <pattern>",
        "when_to_use": "Quick check: is <process> running, and what's its PID / command line?",
        "when_not_to_use": "Production monitoring (use proper observability). Scripted PID lookups — use `pgrep` or `pidof` instead (no need to filter out grep itself).",
        "gotchas": "- `ps aux | grep foo` ALWAYS matches the grep itself unless you filter (`grep -v grep`). The classic gotcha.\n- `pgrep -af <pattern>` is cleaner; `-a` shows full command, `-f` matches against full command line (not just basename).\n- Pre-systemd / pre-cgroup, this was the only way to identify processes. Now: `systemctl status` for services, `docker ps` for containers.",
        "flags": "ps:\n- `a`: show processes of other users\n- `u`: detailed user-oriented output\n- `x`: include processes not attached to a terminal\n- `-ef`: BSD-style is `aux`; SysV-style is `-ef`. Both work on Linux.\n\npgrep:\n- `-a`: show command line\n- `-f`: match against full command line\n- `-u <user>`: scope to a user",
        "examples": "- Is nginx running: `pgrep -af nginx`\n- All python processes: `pgrep -af python`\n- Sort by CPU: `ps aux --sort=-%cpu | head`\n- By memory: `ps aux --sort=-%mem | head`",
        "references": "man ps; man pgrep",
    },
    {
        "slug": "ss-listening-sockets",
        "name": "ss -tlnp (listening TCP sockets + PID)",
        "family": "monitoring",
        "platform": "linux",
        "equivalents": "netstat -tlnp (deprecated); lsof -i :PORT (slower, more general)",
        "command": "ss -tlnp",
        "when_to_use": "Quick: what's listening on what TCP port, owned by which process. Modern replacement for `netstat -tlnp`.",
        "when_not_to_use": "macOS — `ss` isn't standard; use `lsof -iTCP -sTCP:LISTEN -nP`.",
        "gotchas": "- `-p` (process) needs root to show PIDs from other users.\n- `-n` skips DNS / port-name resolution — much faster on busy boxes.\n- `-t` for TCP, `-u` for UDP, `-l` for listening only, `-a` for all states.\n- Drop `-l` to see established connections too: `ss -tnp`.",
        "flags": "- `-t` / `-u`: TCP / UDP\n- `-l`: listening only\n- `-n`: numeric (no DNS)\n- `-p`: show owning process (needs root for full info)\n- `-a`: all states (including TIME_WAIT, CLOSE_WAIT)\n- `-4` / `-6`: address family\n- `state established`: filter by socket state",
        "examples": "- All listeners: `sudo ss -tlnp`\n- Specific port: `sudo ss -tlnp 'sport = :5572'`\n- Connections to a host: `sudo ss -tn 'dst edge-host'`\n- TCP states summary: `ss -s`",
        "references": "man ss",
    },
    {
        "slug": "strace-attach",
        "name": "strace -p PID (debug a running process)",
        "family": "monitoring",
        "platform": "linux",
        "equivalents": "dtruss (macos)",
        "command": "strace -p <pid> -f -e trace=network -o /tmp/strace.out",
        "when_to_use": "A process is hung or misbehaving and you want to see what syscalls it's making. Common: file-IO stalls, network hangs, sleeps.",
        "when_not_to_use": "Production at scale — strace is expensive (every syscall is paused). On hot paths it can slow the process dramatically.\nLow-level performance work — use `perf` or `bpftrace` instead.",
        "gotchas": "- `-f` traces forks (child threads/processes). Without it, a forking process disappears from view.\n- `-e trace=network` (or `=file`, `=signal`, etc.) filters by syscall category — drastically reduces output noise.\n- Strace adds significant overhead — a CPU-bound process may be 10-100x slower while attached.\n- Attaching to PID 1 (init) is almost always a bad idea.\n- Modern alternative for live observation without slowdown: `bpftrace` or `bcc` tools.",
        "flags": "- `-p <pid>`: attach to running process\n- `-f`: trace forked children\n- `-e trace=<category>`: filter syscalls (file, network, signal, process, ipc)\n- `-c`: count, don't dump (summary at end)\n- `-T`: time spent in each syscall\n- `-tt`: timestamp with microseconds\n- `-o <file>`: write to file\n- `-s <n>`: max string length to print (default 32; increase for full strings)",
        "examples": "- All syscalls of running process: `sudo strace -p <pid> -f -o /tmp/strace.out`\n- Just network: `sudo strace -p <pid> -e trace=network`\n- Summary: `sudo strace -p <pid> -c` (Ctrl-C to stop and see summary)\n- Where is it stuck: `cat /proc/<pid>/stack; cat /proc/<pid>/wchan` (faster than strace, doesn't pause)",
        "references": "man strace",
    },

    # ============================ certs ============================
    {
        "slug": "openssl-s-client-cert-chain",
        "name": "openssl s_client -showcerts (inspect cert chain)",
        "family": "certs",
        "platform": "cross-platform",
        "equivalents": "curl -v --cacert <ca> https://host (less detail)",
        "command": "openssl s_client -showcerts -connect <host>:443 -servername <host> < /dev/null",
        "when_to_use": "Inspect the full TLS handshake + cert chain a server presents. Diagnose 'why does my client say this cert is invalid'.",
        "when_not_to_use": "Quick cert info — `openssl x509 -text -in <file>` on a downloaded cert is faster.\nProduction monitoring — Prometheus exporters / managed cert monitoring exist for that.",
        "gotchas": "- WITHOUT `-servername <host>`, SNI isn't sent, and you may get the default cert instead of the one for your host.\n- `< /dev/null` closes stdin so s_client doesn't hang waiting for your HTTP request.\n- The chain is presented bottom-up: leaf cert first, then intermediates. The root is usually NOT in the chain (the client validates against its own trust store).\n- For just the chain: `openssl s_client ... | sed -n '/-----BEGIN CERTIFICATE-----/,/-----END CERTIFICATE-----/p'`\n- This is exactly the test that verified the Acme device cert chain (G1.1/G1.2/G1.4.a/G1.6 in CLAUDE.md).",
        "flags": "- `-connect <host:port>`: target\n- `-servername <host>`: SNI\n- `-showcerts`: dump full chain (not just leaf)\n- `-CAfile <ca-bundle>`: use a specific CA bundle\n- `-verify_return_error`: exit non-zero on verify fail\n- `-tls1_3` / `-tls1_2`: force a TLS version",
        "examples": "- Standard: `openssl s_client -showcerts -connect app.acmefpv.com:443 -servername app.acmefpv.com < /dev/null`\n- Extract just cert PEMs: `openssl s_client ... < /dev/null 2>/dev/null | openssl x509 -outform PEM > leaf.pem`\n- Test custom CA: `openssl s_client ... -CAfile /etc/ssl/certs/my-root.pem`",
        "references": "man s_client",
    },
    {
        "slug": "openssl-x509-text",
        "name": "openssl x509 -text -noout -in <cert>",
        "family": "certs",
        "platform": "cross-platform",
        "equivalents": "step certificate inspect <cert>",
        "command": "openssl x509 -text -noout -in <cert.pem>",
        "when_to_use": "Inspect a downloaded cert's subject / issuer / SANs / validity / extensions / signature algorithm.",
        "when_not_to_use": "JWT or other non-X509 token — use `jwt-cli` or `jq`.",
        "gotchas": "- `-noout` SUPPRESSES the PEM dump at the end. Without it you get human-readable PLUS the PEM (ugly).\n- The cert must be in PEM format (BEGIN CERTIFICATE / END CERTIFICATE). For DER: `-inform DER`.\n- For chain files: each cert is rendered separately; use `awk` or `csplit` to split.\n- The 'Subject Alternative Name' line is where hostname matching happens. CN (Common Name) is largely deprecated.",
        "flags": "- `-text`: human-readable\n- `-noout`: don't include the PEM\n- `-in <file>`: input\n- `-inform PEM|DER`: input format\n- `-subject` / `-issuer` / `-dates` / `-fingerprint`: just one field\n- `-purpose`: what this cert is good for (server / client / signing)",
        "examples": "- Inspect: `openssl x509 -text -noout -in /etc/ssl/certs/my.crt`\n- Just the SAN line: `openssl x509 -text -noout -in cert.pem | grep -A1 'Subject Alternative Name'`\n- Just dates: `openssl x509 -dates -noout -in cert.pem`\n- DER input: `openssl x509 -inform DER -in cert.der -text -noout`",
        "references": "man x509",
    },

    # ============================ text ============================
    {
        "slug": "jq-essentials",
        "name": "jq essentials (.field, [], select, map)",
        "family": "text",
        "platform": "cross-platform",
        "equivalents": "yq (yaml); fx (interactive)",
        "command": "<json-source> | jq '.<path>'\n<json-source> | jq '.[] | select(.status == \"active\")'\n<json-source> | jq -r '.items[] | \"\\(.id)\\t\\(.name)\"'",
        "when_to_use": "Parse / filter / reshape JSON on the command line. The rote's CLI uses jq throughout.",
        "when_not_to_use": "YAML — use `yq` (jq-syntax-compatible).\nDeeply complex transformations — use a real script (Python, JS).\nXML — use `xmlstarlet`.",
        "gotchas": "- `-r` / `--raw-output` strips JSON quoting on STRING output. Without it `jq '.name'` returns `\"foo\"`; with `-r` returns `foo`.\n- `-c` / `--compact-output`: one line per result (for piping to xargs / writing to file).\n- jq's `select(...)` returns the matching item; `map(select(...))` returns the array of matching items.\n- `\\(.field)` is string interpolation; `\"\\(.a)\\t\\(.b)\"` builds tab-separated output.\n- `if-then-else` and `// default` for null handling: `.maybe_missing // \"default\"`.",
        "flags": "- `-r`: raw output (no JSON quotes on string results)\n- `-c`: compact (one line per result)\n- `-n`: don't read stdin (start from null)\n- `--arg <name> <value>`: pass string variable\n- `--argjson <name> <json>`: pass JSON variable\n- `-S`: sort keys in output (for diffs)",
        "examples": "- Field: `cat resp.json | jq '.data.users'`\n- Filter array: `jq '.users[] | select(.active == true)'`\n- Build object: `jq '{name, email}'`\n- TSV for table output: `jq -r '.users[] | [.id, .name, .email] | @tsv'`\n- Count: `jq '.users | length'`\n- Sum: `jq '[.transactions[].amount] | add'`",
        "references": "https://stedolan.github.io/jq/manual/",
    },
    {
        "slug": "sed-in-place",
        "name": "sed -i 's/from/to/g' (in-place file edit)",
        "family": "text",
        "platform": "cross-platform",
        "equivalents": "perl -pi -e 's/from/to/g' (works identically on mac+linux); GNU sed (linux); BSD sed (macos)",
        "command": "sed -i 's/<pattern>/<replacement>/g' <file>",
        "when_to_use": "Quick in-place text substitution in one file. For multi-file, prefer the library's `find-replace-tree.sh` (handles backups, gitignore, etc.).",
        "when_not_to_use": "Codebase-wide replace — use `scripts/find-replace-tree.sh` (backup + glob filter + dry-run).\nStructural edits — use a real parser (Tree-sitter, AST tools).\nIrreversible edits without backup — at minimum add `.bak` suffix: `sed -i.bak 's/.../.../'`.",
        "gotchas": "- macOS (BSD sed) REQUIRES an extension after `-i`: `sed -i '' 's/.../.../' file`. GNU sed (linux): `sed -i 's/.../.../' file`. Use `sed -i.bak 's/.../.../'` for portable code (works on both, produces .bak files you can delete).\n- The delimiter is by convention `/` but ANY char works. Use a different delimiter when your patterns contain slashes: `sed 's|/foo|/bar|g'`.\n- `&` in the replacement is the WHOLE match. `\\1`, `\\2`, etc. are capture groups (with `-E` or escaped `\\(...\\)`).\n- For multi-line / structural edits, sed is the wrong tool. Use `awk` or a real script.",
        "flags": "- `-i [<ext>]`: in-place; with ext (e.g. `.bak`) for a backup; without, modify directly\n- `-E`: extended regex (so `+`, `?`, `()` work without `\\`)\n- `-n`: silent (only print what you tell it to with `p`)\n- `-e <script>`: explicit script (allows multiple)\n- `-f <scriptfile>`: read commands from file",
        "examples": "- Replace one file: `sed -i 's/old_string/new_string/g' config.yaml`\n- Portable backup-first: `sed -i.bak 's/foo/bar/g' file.txt`\n- Multi-line delete: `sed -i '/^# DELETE_ME/,/^# END_DELETE/d' file.txt`\n- With non-slash delimiter: `sed -i 's|/old/path|/new/path|g' file.txt`",
        "references": "man sed",
    },
    {
        "slug": "grep-recursive",
        "name": "grep -rE / rg (recursive grep)",
        "family": "text",
        "platform": "cross-platform",
        "equivalents": "ripgrep (`rg`) — much faster + respects .gitignore by default; ack",
        "command": "grep -rEn '<regex>' <path>      # POSIX, in stdlib\nrg '<regex>' <path>             # ripgrep, faster + smarter",
        "when_to_use": "Find a pattern across a tree. For dev work, `rg` (ripgrep) is the modern choice — 10-100x faster + respects .gitignore.",
        "when_not_to_use": "A specific file — just `grep <pattern> <file>`.\nNeed line-level structure (replacement, multi-pattern) — use the library's `find-replace-tree.sh` for write ops.",
        "gotchas": "- POSIX grep without `-E` uses BASIC regex (no `+`, `?`, `()` without escaping). `-E` enables extended regex (most people's mental model).\n- `-r` follows symlinks by default — can produce infinite loops in weird trees. Use `-R` to follow (POSIX) but watch out.\n- `--include='*.ts'` filters by glob. `--exclude='*.bak'` skips.\n- `rg` respects `.gitignore`, `.ignore`, `.rgignore` automatically. Pass `--no-ignore` to disable.\n- For literal strings (not regex), use `grep -F` / `rg -F`.\n- For just files (not lines): `grep -l` / `rg -l`.",
        "flags": "grep:\n- `-r`: recursive\n- `-E`: extended regex\n- `-n`: line numbers\n- `-i`: case-insensitive\n- `-l`: only filenames\n- `-c`: count per file\n- `-F`: fixed (literal) string\n- `--include`, `--exclude`\n- `-C N`: N lines of context\n\nrg:\n- All the above plus:\n- `-t <type>` / `-T <type>`: file-type filter (`rg -t py 'foo'`)\n- `--hidden`: include dotfiles\n- `--no-ignore`: ignore .gitignore\n- `-S` / `--smart-case`: lowercase = insensitive, mixed = sensitive",
        "examples": "- POSIX: `grep -rEn 'TODO' src/`\n- Filter type: `grep -rEn --include='*.ts' 'useState' src/`\n- ripgrep modern: `rg 'TODO' src/`\n- Just files: `rg -l 'export function' src/`\n- Context: `rg -C 3 'Error' /var/log/`",
        "references": "man grep; https://github.com/BurntSushi/ripgrep",
    },

    # ============================ process ============================
    {
        "slug": "nohup-disown",
        "name": "nohup + disown (background a long process)",
        "family": "process",
        "platform": "cross-platform",
        "equivalents": "systemd-run --user (systemd); tmux / screen (with attach later); pm2 (node)",
        "command": "nohup <cmd> > <logfile> 2>&1 </dev/null &\ndisown",
        "when_to_use": "Start a long-running command from a shell, then log out without killing it.",
        "when_not_to_use": "Production daemons — use systemd / supervisord / a process manager. nohup is for ad-hoc.\nNeeding to attach back later — use `tmux` or `screen`.",
        "gotchas": "- WITHOUT `</dev/null`, the process inherits your terminal's stdin and can hang on read attempts.\n- WITHOUT `> <log> 2>&1`, output goes to `nohup.out` in the current dir — surprise file.\n- `disown` removes the job from the shell's job table so the shell won't send SIGHUP on exit (nohup blocks SIGHUP via the syscall but jobs-table state can still confuse).\n- The combination `nohup ... &` + `disown` is belt + suspenders. Either alone usually works; both together always works.",
        "flags": "nohup: no flags worth knowing — it just sets up the signal handler and execs.\n\ndisown:\n- `-h`: don't remove from job table, just mark to not receive HUP\n- `-a`: all jobs\n- `%<n>`: specific job number",
        "examples": "- Run + detach: `nohup ./long-task.sh > /tmp/long-task.log 2>&1 </dev/null &; disown`\n- Server start (rote uses this): `nohup ./server/start.sh >> data/server.log 2>&1 </dev/null &`\n- More modern alt: `systemd-run --user --scope --unit=my-task /path/to/task` (gets you cgroup + log isolation)",
        "references": "man nohup; man disown",
    },
    {
        "slug": "tmux-basics",
        "name": "tmux basics (new / attach / detach)",
        "family": "process",
        "platform": "cross-platform",
        "equivalents": "screen (older, similar); zellij (modern)",
        "command": "tmux new -s <name>       # create + attach\ntmux attach -t <name>    # reattach\ntmux ls                  # list sessions\n# Inside: Ctrl-b d = detach; Ctrl-b c = new window; Ctrl-b n/p = next/prev",
        "when_to_use": "Long-running processes you want to leave running on a remote box; multi-pane terminal layouts; collaborative shell sessions.",
        "when_not_to_use": "Single short command — use `nohup` + `&`.\nProduction services — use systemd.",
        "gotchas": "- The prefix key is `Ctrl-b` by default. Most people remap to `Ctrl-a` (more ergonomic) in `~/.tmux.conf`.\n- Detaching is `Ctrl-b d` (NOT `exit`, which kills the shell).\n- A session can have many windows (Ctrl-b c to create), and each window many panes (Ctrl-b % to split).\n- `tmux kill-session -t <name>` kills the named session and everything in it.\n- For sharing a session with another user: `tmux new -s shared` then have them `tmux attach -t shared` (with appropriate perms).",
        "flags": "- `new -s <name>`: create named session\n- `new -d -s <name> <cmd>`: detached start with a command\n- `attach -t <name>`: reattach\n- `ls`: list sessions\n- `kill-session -t <name>` / `kill-server`: cleanup\n- `send-keys -t <name>:<window> '<keys>' Enter`: scriptable input",
        "examples": "- Start: `tmux new -s deploy`\n- Detach: `Ctrl-b d`\n- Reattach: `tmux attach -t deploy`\n- Run a one-off in background: `tmux new -d -s background-job 'sleep 1000; echo done'`\n- Script-friendly: `tmux send-keys -t deploy:0 'systemctl restart api' Enter`",
        "references": "man tmux",
    },
    {
        "slug": "timeout-bound-execution",
        "name": "timeout <seconds> <cmd> (kill if it runs too long)",
        "family": "process",
        "platform": "cross-platform",
        "equivalents": "gtimeout (mac, via brew install coreutils); manual sleep + kill",
        "command": "timeout [<sig>] <duration> <cmd> [<arg>...]",
        "when_to_use": "Bound how long a command can run. Critical for cron jobs, scripts that might hang on network, CI steps.",
        "when_not_to_use": "Production work — bake timeouts into the application code (HTTP client timeouts, connection pools, etc.). `timeout` is a coarse outer-layer guard.",
        "gotchas": "- Exit code 124 means 'timed out'. The rote run_script handler maps 124 to outcome 'timeout'.\n- Default signal is SIGTERM. Use `-s SIGKILL` for processes that ignore SIGTERM.\n- `--kill-after=<dur>` sends SIGKILL after additional <dur> if the original signal didn't work — belt + suspenders.\n- macOS doesn't ship `timeout`; install with `brew install coreutils` (binary becomes `gtimeout`) or alias.",
        "flags": "- `-s` / `--signal=<sig>`: signal to send (default TERM)\n- `-k` / `--kill-after=<dur>`: SIGKILL after extra <dur>\n- `--preserve-status`: exit with the child's exit code, not 124 on timeout\n- `--foreground`: don't make the child a separate process group",
        "examples": "- Bound a curl: `timeout 30 curl -fsS https://slow.host/`\n- Reliably kill: `timeout -k 10 60 ./flaky-script.sh` (TERM after 60s; KILL 10s later if still alive)\n- CI step: `timeout 1800 npm test || echo 'test suite timed out'` (kept inline; exit 124 on timeout)",
        "references": "man timeout",
    },
]


def render_command(c: dict) -> str:
    refs = c.get("references", "")
    return (
        "---\n"
        f"slug: {c['slug']}\n"
        f"name: {c['name']}\n"
        f"family: {c['family']}\n"
        f"platform: {c.get('platform', '')}\n"
        f"equivalents: {c.get('equivalents', '')}\n"
        f"references: {refs}\n"
        "---\n\n"
        "# Command\n"
        f"```sh\n{c['command'].strip()}\n```\n\n"
        "# When to use\n"
        f"{c['when_to_use'].strip()}\n\n"
        "# When NOT to use\n"
        f"{c['when_not_to_use'].strip()}\n\n"
        "# Gotchas\n"
        f"{c['gotchas'].strip()}\n\n"
        "# Flags\n"
        f"{c['flags'].strip()}\n\n"
        "# Examples\n"
        f"{c.get('examples', '').strip()}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/path/to/rote")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = Path(args.root)
    cmd_dir = root / "commands"
    written = 0
    skipped = 0
    for c in COMMANDS:
        family_dir = cmd_dir / c["family"]
        family_dir.mkdir(parents=True, exist_ok=True)
        path = family_dir / f"{c['slug']}.md"
        content = render_command(c)
        if path.exists() and path.read_text() == content:
            skipped += 1
            continue
        if args.dry_run:
            print(f"[dry-run] would write {path}")
        else:
            path.write_text(content)
            print(f"+ {path}")
        written += 1
    print(f"\n{written} written, {skipped} unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
