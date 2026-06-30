---
slug: multi-agent-orchestration
name: Multi-Agent Orchestration
category: ai
intent: Decompose a task across multiple specialized LLM agents that work concurrently or in pipeline
references: Anthropic 'Building effective agents'; CrewAI; LangGraph
---

# When to use
The task naturally decomposes: research → write → review.  Each step has different skills / prompts.

Independent work-items can run in parallel (review 5 files concurrently, each by a separate agent).

Context budgets are tight — splitting protects the main agent's context window.

Adversarial verification: one agent generates, another verifies independently.

# When NOT to use
The task is genuinely sequential and small — multi-agent is overhead.

Coordination cost exceeds the benefit — every additional agent is a context window + LLM call.

You're using agents for things one agent does better — many tasks benefit from one coherent mind.

# Structure
Orchestrator agent (the main loop) spawns specialist agents.  Specialists work in parallel.  Results are aggregated.  Optional adversarial: one writes, another critiques.  Tools: Anthropic subagents, LangGraph, CrewAI, custom workflows.

# Example
Claude Code's Workflow tool is multi-agent orchestration: fan-out specialists, aggregate, verify, synthesize.

# Relationships
Pairs with ReAct (each agent runs its own loop).  Pairs with skill-based-prompting (specialists have skill stacks).  Adversarial-verify pattern is multi-agent at its core.
