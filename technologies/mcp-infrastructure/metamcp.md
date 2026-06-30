---
slug: metamcp
name: MetaMCP
category: mcp-infrastructure
implements_patterns: mcp-aggregator-proxy, facade-pattern
tags: self-hosted, offline-capable, open-source, mcp
references: MetaMCP repo; references/metamcp-registration.md
---

# When to use
You have multiple downstream MCP servers and want LLM clients to see them through one endpoint.

You want central auth + namespacing across many tool surfaces.

Acme uses MetaMCP on edge-host to aggregate the rote MCP server + others, exposed at /metamcp/{endpoint}/mcp with Bearer auth.

# When NOT to use
You have only one MCP server — direct connection.

The aggregator adds latency you can't afford.

You don't need cross-tool aggregation, just routing.

# Limitations
- Subprocess-launched MCP servers can be flaky to restart.
- Auth is api_key-based today; mTLS would be stronger.
- The aggregator is a SPOF unless replicated.

# Cost
Free open-source.  Light compute.

# Alternatives
Direct MCP connection per client.  Custom proxy with auth middleware.  Future: standardized MCP gateways.
