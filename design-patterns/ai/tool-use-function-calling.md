---
slug: tool-use-function-calling
name: Tool Use / Function Calling
category: ai
intent: Let the LLM trigger external actions by emitting structured tool-call requests that the runtime executes
references: OpenAI Function Calling; Anthropic Tool Use; MCP spec
---

# When to use
The LLM needs to act on the world (read a file, query a DB, run a script, call an API).

The user expects the model to operate on the runtime, not just answer in text.

You want predictable, structured arguments instead of regex-parsing a free-text answer.

# When NOT to use
The model can answer in text without acting — don't reach for tools.

The tool surface is huge and the model picks the wrong tool — narrow the surface or use an aggregator (MetaMCP).

Tools have irreversible side effects and you don't have user confirmation — gate destructive tools.

# Structure
Tools declared with schemas (name, description, input shape).  LLM emits a tool_call block.  Runtime validates args, executes, returns the result as a tool_result.  Loop until the model produces a regular response.

# Example
```python
tools = [{
  "name": "find_script",
  "description": "Semantic-search reusable scripts",
  "input_schema": {
    "type": "object",
    "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
    "required": ["query"]
  }
}]
```

# Relationships
Foundation of ReAct.  Pairs with structured-output-with-schema (schema = the tool's input contract).  Pairs with mcp-aggregator-proxy (MCP = a tool-use protocol).
