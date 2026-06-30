---
slug: author-claude-md
name: Author a CLAUDE.md
category: project-init
tags: claude-md, conventions, bootstrap, context
---

# Prompt

Write (or update) a CLAUDE.md for this repo that makes a fresh session productive immediately. Derive everything from the actual code — do not invent.

Include only what's non-obvious and load-bearing:
- How to build, run, test, and lint (exact commands).
- Architecture in 3–6 bullets: the modules and their boundaries.
- Conventions that must be followed (naming, error handling, formatting, commit style) — with a one-line why where it isn't obvious.
- Gotchas / footguns a newcomer would hit.
- What NOT to touch and why (generated files, vendored code, hard rules).

Keep it tight and scannable. Omit anything discoverable in 5 seconds. Prefer pointers ("see ${X}") over duplicating content that will drift.

# When to use

Bootstrapping a repo's persistent context so future sessions don't re-derive the basics each time.
