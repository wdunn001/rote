---
slug: claude-code-skill-pipeline
name: Claude Code skills + auto-memory + MCP server (this repo)
technologies: metamcp
patterns: skill-based-prompting, rag-retrieval-augmented-generation, mcp-aggregator-proxy, tool-use-function-calling
context: wdunn001/rote — Claude Code integration
outcome: success
references: https://github.com/wdunn001/rote
---

# What worked
- 5 skills under ~/.claude/skills/ + memory entry + MCP server + OpenAPI = ANY LLM client can use the same tools
- Symlinked skills (--mode symlink) flow edits back to the repo for commit
- Bootstrap script (rote bootstrap) sets up backend + MCP + client configs + skills + verify in one command on a fresh machine
- ROADMAP items get auto-recorded as anti-patterns + design patterns get cross-linked to technologies

# What didn't
- Required a rule-strengthening step to actually change behavior; infrastructure alone wasn't enough
- Initial use_count is always zero — patterns are documented but the LLM has to actively reach for them; needs ongoing reinforcement

# When to reuse
- Any LLM-augmented workflow where you want session-persistent knowledge
- When the training data is mediocre on your problem domain (cite a curated catalog instead)

# When to avoid
- One-off sessions where the setup cost exceeds the benefit
- When the catalog isn't curated — uncurated catalogs are training-data with extra steps
