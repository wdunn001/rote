---
slug: persistent-data-under-claude-config-dir
title: Storing real persistent data (databases, vaults) under ~/.claude/ instead of a user-owned project location
hit_count: 1
token_cost: medium — once discovered the user has to relocate everything; meanwhile their data feels hidden + un-versionable + un-backupable
---

# Symptom

Claude builds a persistent backend (database, vault, scripts, secrets) and places the whole tree under `~/.claude/` because that's where companion skill files live. User pushes back: "where is my database... under a .claude folder doesn't sound right."

# Root cause

`~/.claude/` is the right home for Claude Code's own configuration (skills, settings, project metadata). It is the WRONG home for:
- Application databases (sqlite files, vec stores)
- Secret vaults the user is meant to inspect / version / back up
- Reusable scripts the user might share between machines
- Anything the user should be able to point a file explorer at and treat as "their own project"

The mistake happens because the SKILL.md files genuinely belong under `~/.claude/skills/`, and it's easy to colocate the data the skills use in the same place. The two concerns drift together until the user notices and asks why their database is buried under a hidden Claude config dir.

# Remedy

Split the two concerns at design time:

1. **Skill definitions** stay at `~/.claude/skills/<skill-name>/SKILL.md`. These ARE Claude Code config.
2. **Backing data** (database, vault, reusable scripts, persistent state) lives at a user-owned path the user picks. `~/dev/<thing>/` for Windows-visible, `/home/<user>/<thing>/` for WSL-native. Either way, it should be the user's first-class location.
3. Skills reference the backing location via **absolute path** in their SKILL.md.
4. The backing location is **its own git repo** with appropriate `.gitignore` for secrets + databases + venvs.

When you find yourself writing into `~/.claude/` for anything other than a SKILL.md, a `settings.json`, a project memory file, or a tool registration — STOP. That data needs a different home.

# Detection

Anytime a project under `~/.claude/` accumulates more than:
- A `SKILL.md`
- A small `.json` config
- Memory entries

…it's grown beyond what `~/.claude/` should hold. Move it.

Greppable smell: a `.gitignore` or a `requirements.txt` or a database file under `~/.claude/`. None of those should be there.

# See also

- The August 2026 relocation event: `~/.claude/rote/` → `/path/to/rote/` (its own git repo at https://github.com/wdunn001/rote)
- [[rote]] skill — points at the relocated home
