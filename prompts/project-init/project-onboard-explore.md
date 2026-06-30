---
slug: project-onboard-explore
name: Onboard to an Unfamiliar Repo
category: project-init
tags: onboarding, exploration, codebase-map
---

# Prompt

Build me a working mental model of this repo before we change anything.

1. Identify the stack, entry points, and how it runs/builds/tests (cite the files).
2. Map the top-level architecture: the main modules/services and how they talk.
3. Find the conventions actually in use (naming, error handling, test style, dependency injection) — by reading code, not guessing.
4. Locate where ${AREA_OF_INTEREST} lives and trace one representative path through it end to end.
5. Flag anything surprising: dead code, conflicting patterns, missing tests, footguns.

Output a concise map (file:line references, clickable) — not a file dump. End with the 3 files I should read first to be productive here.

# When to use

Starting work in a codebase you don't know yet — front-load understanding so later edits fit the grain of the project.
