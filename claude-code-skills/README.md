# Claude Code skills + memory entry

Four skills + one memory entry that turn this repo into a fully-integrated Claude Code experience. Each `SKILL.md` is auto-discovered by Claude Code's Skill tool when present under `~/.claude/skills/<name>/SKILL.md`.

## What's here

| File | What it does |
|---|---|
| [`rote/SKILL.md`](./rote/SKILL.md) | Six hard rules: never write to `/tmp/`, always `rote find` first, use the generic shapes for find/replace + copy + ssh, scaffold new entries with `rote new`. The "library first" workflow. |
| [`secret-handling/SKILL.md`](./secret-handling/SKILL.md) | The vault routing flow + the five "never" rules around secret values. Claude never sees secret bytes — only NAMES. |
| [`local-delegate/SKILL.md`](./local-delegate/SKILL.md) | Defer mechanical work to edge-host (Ollama / sglang / MetaMCP). Capability taxonomy + best-delegate routing + outcome logging. |
| [`chronicle/SKILL.md`](./chronicle/SKILL.md) | Session post-mortems with teeth — what shipped, what bit us, what to do next. Auto-records §2 findings into the anti-pattern catalog. |
| [`memory/arch-rote-context-system.md`](./memory/arch-rote-context-system.md) | Memory entry so future Claude Code sessions know the system exists before searching for it. |

## Install on this machine

```bash
# One command, idempotent.  Default mode is "copy" — safe for prod.
~/.claude/rote/scripts/install-claude-code-skills.sh
# or the CLI shortcut:
rote skills-install
```

What it does:

1. Copies (or symlinks with `--mode symlink`) each `SKILL.md` to `~/.claude/skills/<name>/SKILL.md`
2. Copies the memory entry to `~/.claude/projects/<project>/memory/`
3. Adds the one-line index entry to `~/.claude/projects/<project>/memory/MEMORY.md` if not present
4. Backs up any existing same-named file as `.bak.<timestamp>` (skip with `--no-backup`)

After install, **restart Claude Code** so the new skills get picked up. Verify with: in any session, type `/rote` — if the skill loads, the install worked.

### Maintainer workflow (`--mode symlink`)

If you're editing skills in-repo and want changes to live-flow without a re-install, use symlinks:

```bash
~/.claude/rote/scripts/install-claude-code-skills.sh --mode symlink
```

The targets under `~/.claude/skills/` become symlinks back to the repo. Edit in either location — same file. `git diff` shows the edits.

### Other useful flags

```bash
--skills chronicle,rote     # subset (default: all four)
--memory-project-dir <slug>           # if your project dir isn't -home-user-dev
--no-memory                           # skip the memory entry
--no-backup                           # don't make .bak copies
--dry-run                             # preview without writing
```

## How Claude Code discovers + uses these

- **Skills**: Claude Code scans `~/.claude/skills/*/SKILL.md` on each session and exposes them as `/skill-name` slash commands. The `description:` frontmatter tells the LLM when to invoke. See https://docs.claude.com/en/docs/claude-code/skills.
- **Memory**: anything under `~/.claude/projects/<slug>/memory/MEMORY.md` is loaded into context at session start, providing persistent cross-session knowledge. The arch entry points at this repo so the LLM knows the system exists before its first search.

## Integrating from a fresh clone on a new machine

```bash
git clone git@github.com:wdunn001/rote.git /path/to/rote
cd /path/to/rote
./scripts/bootstrap-context-system.sh
```

`bootstrap-context-system.sh` calls `install-claude-code-skills.sh` automatically if the skills aren't present, so this single command sets up the backend + MCP venv + MCP client configs + Claude Code skills + memory entry + runs the smoke test.

## What if I'm using a different working directory than ~/dev/?

Claude Code encodes the working dir as the project memory directory name. For `~/dev/` the encoded form is `-home-user-dev`. For a different working dir, pass the encoded form:

```bash
rote skills-install --memory-project-dir -home-myuser-projects-foo
```

To find your encoding: `ls ~/.claude/projects/` after using Claude Code once in that directory.
