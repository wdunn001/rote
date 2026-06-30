# OpenAPI integration — use the rote from any function-calling LLM

The FastAPI server auto-generates an OpenAPI 3.1 spec at:

```
http://127.0.0.1:5572/openapi.json
```

and a Swagger UI at `http://127.0.0.1:5572/docs`. Every function-calling LLM ecosystem can read this and present the rote as native tool calls. This is the path for LLMs that aren't MCP-aware (yet).

## What you give the LLM

Three things, depending on the runtime:

1. **System prompt** describing when to use the tools (use the `rote` skill's text — `~/.claude/skills/rote/SKILL.md`).
2. **Tool definitions** derived from the OpenAPI spec.
3. **A relay**: code that, when the LLM emits a tool call, makes the matching HTTP request and feeds the response back.

## OpenAI function calling

```python
import openai, httpx, json

# 1. Fetch the spec once at startup.
spec = httpx.get("http://127.0.0.1:5572/openapi.json").json()

# 2. Convert each operation to an OpenAI tool.
def openapi_to_openai_tools(spec: dict) -> list[dict]:
    tools = []
    for path, methods in spec.get("paths", {}).items():
        for method, op in methods.items():
            if method.upper() not in {"GET", "POST", "PATCH", "DELETE"}:
                continue
            params_schema = {"type": "object", "properties": {}, "required": []}
            # path + query params
            for p in op.get("parameters", []):
                params_schema["properties"][p["name"]] = p.get("schema", {"type": "string"})
                if p.get("required"):
                    params_schema["required"].append(p["name"])
            # body
            body = op.get("requestBody", {})
            if "application/json" in body.get("content", {}):
                body_schema = body["content"]["application/json"].get("schema", {})
                params_schema["properties"]["body"] = body_schema
                if body.get("required"):
                    params_schema["required"].append("body")
            tools.append({
                "type": "function",
                "function": {
                    "name": op.get("operationId") or f"{method}_{path.replace('/', '_')}",
                    "description": op.get("summary") or op.get("description") or "",
                    "parameters": params_schema,
                },
            })
    return tools

tools = openapi_to_openai_tools(spec)

# 3. Run a chat completion with the tools.
client = openai.OpenAI()
messages = [
    {"role": "system", "content": "You can call the local Rote tools to discover scripts, defer work to local LLMs, and manage secrets safely."},
    {"role": "user", "content": "Find me a script for injecting env secrets."},
]
resp = client.chat.completions.create(model="gpt-4o-mini", messages=messages, tools=tools)

# 4. Relay tool calls back to the HTTP API.
for call in resp.choices[0].message.tool_calls or []:
    fn = call.function
    args = json.loads(fn.arguments)
    # Pick the OpenAPI path that matches fn.name.  In production keep a
    # name → (method, path) map you built when generating the tools.
    # Here a thin example:
    if fn.name == "search_scripts_scripts_search_post":
        r = httpx.post("http://127.0.0.1:5572/scripts/search", json=args.get("body", {}))
        result = r.json()
    # ... etc.
```

## Anthropic API tool use (non-MCP)

If you're using the raw Anthropic API (not Claude Desktop with MCP), do the same OpenAPI → tools conversion:

```python
import anthropic, httpx, json
spec = httpx.get("http://127.0.0.1:5572/openapi.json").json()

def openapi_to_anthropic_tools(spec: dict) -> list[dict]:
    # Anthropic uses {name, description, input_schema} per tool.
    tools = []
    for path, methods in spec.get("paths", {}).items():
        for method, op in methods.items():
            if method.upper() not in {"GET", "POST", "PATCH", "DELETE"}:
                continue
            input_schema = {"type": "object", "properties": {}, "required": []}
            for p in op.get("parameters", []):
                input_schema["properties"][p["name"]] = p.get("schema", {"type": "string"})
                if p.get("required"):
                    input_schema["required"].append(p["name"])
            body = op.get("requestBody", {})
            if "application/json" in body.get("content", {}):
                input_schema["properties"]["body"] = body["content"]["application/json"].get("schema", {})
                if body.get("required"):
                    input_schema["required"].append("body")
            tools.append({
                "name": op.get("operationId") or f"{method}_{path.replace('/', '_')}",
                "description": op.get("summary") or op.get("description") or "",
                "input_schema": input_schema,
            })
    return tools

client = anthropic.Anthropic()
resp = client.messages.create(
    model="claude-opus-4-8",  # or whichever current model
    max_tokens=2048,
    tools=openapi_to_anthropic_tools(spec),
    messages=[{"role": "user", "content": "Defer summarizing this log to a local delegate."}],
)
```

## Gemini / Google AI

Same pattern — Gemini's `FunctionDeclaration` shape matches the OpenAPI parameter object 1:1.

## Local Ollama / sglang with function calling

Newer Ollama builds (and sglang) speak OpenAI-compatible function calling on `/v1/chat/completions`. The exact same OpenAI snippet above works pointed at `http://edge-host:11434/v1` (Ollama) or `http://edge-host:30002/v1` (sglang).

**Bootstrapping irony:** a local LLM that can call the rote can defer its own work to another local LLM via the delegate registry. That's the "any LLM uses the same tools" loop.

## Stable operation IDs

The FastAPI server names each operation. To keep tool definitions stable across versions, lock down `operation_id` per endpoint in `app.py`:

```python
@app.post("/scripts/search", operation_id="search_scripts")
def search_scripts(...):
    ...
```

If you generate tools at runtime from a live `/openapi.json`, the LLM can't rely on a particular operation ID until they're pinned. Most clients don't care if you regenerate every session, but pinning helps if you cache the tool list.

## Security considerations when not on localhost

The API today trusts everything that can reach `127.0.0.1`. Before exposing it over a network:

- See ROADMAP item #7 (Auth for non-localhost).
- Until that lands, run the LLM and the API on the same host (e.g., edge-host running both the local model and a co-located rote instance) so the loopback boundary is preserved.

## Why prefer MCP when both work

- MCP clients negotiate tool lists during the protocol handshake; OpenAPI clients have to fetch + transform the spec themselves.
- MCP standardizes auth flows (forthcoming); OpenAPI relies on the client's HTTP layer.
- MCP carries structured progress + cancellation; OpenAPI tools are single-shot.

For programmatic integrations (a job that uses Anthropic API to summarize log batches), OpenAPI is the simpler path. For interactive multi-tool LLM clients (Cursor, Claude Desktop), MCP is the better fit.
