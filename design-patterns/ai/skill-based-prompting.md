---
slug: skill-based-prompting
name: Skill-Based Prompting
category: ai
intent: Modular, named instructions the LLM can opt into per task instead of one giant system prompt
references: Anthropic Claude Code skills docs
---

# When to use
Different task types need different rules / personas / tool sets.

System prompts are getting too long to maintain or fit in context.

You want behavior to be discoverable (`/skill-name` slash commands).

Examples: Claude Code skills (chronicle, rote, secret-handling, design-patterns), task-specific prompt templates.

# When NOT to use
There's only one task class — over-modularization adds discovery cost.

Skills become invisible to the model (it never reaches for them) — they're not useful at the bottom of a long prompt.

Skills overlap so much they confuse the model on selection.

# Structure
Skill file = name + when-to-invoke description + rules + cross-references.  LLM client surfaces skills as discoverable commands.  Selection is either user-triggered (slash command) or model-decided (description matches task).

# Example
```markdown
---
name: design-patterns
description: ALWAYS invoke before designing a new class hierarchy, service layer, resilience layer, or AI-augmented feature. Returns proven patterns from the catalog so the LLM doesn't reinvent from training data.
---

(skill body)
```

# Relationships
Pairs with rag-retrieval-augmented-generation (skill content can include retrieved chunks).  Pairs with tool-use-function-calling (skills often imply tool sets).  Used throughout this library.
