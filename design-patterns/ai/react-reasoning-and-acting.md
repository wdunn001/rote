---
slug: react-reasoning-and-acting
name: ReAct (Reasoning + Acting)
category: ai
intent: Interleave reasoning steps with tool-use actions so the LLM can investigate before answering
references: Yao et al. 'ReAct: Synergizing Reasoning and Acting'
---

# When to use
The user's question requires multi-step lookups / actions where the next step depends on prior results.

Tools are available (search, calculator, code execution, MCP servers).

You want the model's reasoning visible / auditable.

Classic shape: 'Thought → Action → Observation → Thought → ... → Final Answer.'

# When NOT to use
A single tool call suffices — the reasoning loop is overhead.

Tools are expensive and the model misuses them — guardrail the loop with budgets.

Latency is critical — multiple LLM turns + tool calls compound.

# Structure
System prompt enables tools.  Each turn: LLM either (a) thinks aloud, (b) calls a tool, or (c) finalizes.  Run until 'final answer' or budget exhausted.  Modern frameworks: OpenAI function calling, Anthropic tool use, MCP.

# Example
Claude Code agent loop IS ReAct.  Each turn: Claude thinks, then either calls a tool (Read, Bash, Skill) or answers.

# Relationships
Foundation of agentic LLM apps.  Pairs with tool-use-function-calling (the mechanism).  Pairs with rag-retrieval-augmented-generation (retrieval is a tool).  Pairs with structured-output-with-schema (force structured tool args).
