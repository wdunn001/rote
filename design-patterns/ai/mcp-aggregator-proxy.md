---
slug: mcp-aggregator-proxy
name: MCP Aggregator / Proxy
category: ai
intent: Expose multiple downstream MCP servers as a single endpoint so clients see one unified tool surface
references: MCP spec; MetaMCP
---

# When to use
Multiple MCP servers (rote, codebase tools, deployment tools) but LLM clients want one connection.

You want central auth / rate-limit / audit across many tool surfaces.

Tools live on different hosts; a proxy reaches them on the LLM's behalf.

Example: MetaMCP on edge-host aggregates this library's MCP server + others.

# When NOT to use
One MCP server is enough — direct connection.

The aggregator becomes a single point of failure with no high-availability story.

The latency cost of the proxy hop swamps the convenience.

# Structure
Aggregator presents a unified tools/list (union of downstream tools).  Each tool call is routed to the right downstream server.  Auth + session state managed at the aggregator boundary.

# Example
MetaMCP at http://edge-host:12008/metamcp/{endpoint}/mcp with Bearer auth proxies to N downstream MCP servers per endpoint namespace.  Any LLM connecting through MetaMCP inherits ALL of the aggregated tools.  See references/metamcp-registration.md.

# Relationships
Variant of facade-pattern / adapter for the MCP world.  Pairs with tool-use-function-calling (MCP is the protocol).  Foundation of the 'any LLM uses the same tools' story.
