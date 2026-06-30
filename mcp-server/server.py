"""
Rote — MCP server (FastMCP / stdio).

A thin protocol adapter that exposes the local Rote HTTP API
(127.0.0.1:5572 by default) as MCP tools.  Any MCP client can connect to
this and discover scripts, dispatch to local delegates, manage anti-patterns,
read vault names, and inject vault secrets into target .env files — all
without seeing a single secret value.

Design rules:
- Source of truth stays in the FastAPI server + the SQLite DB.  This file
  is stateless.  Restart anytime; reconnect MCP client; works.
- Tools NEVER return vault values.  Vault endpoints return names + byte
  sizes only.  inject() returns counts only.
- All tool failures surface as MCP errors (raise), not silent empty
  responses, so the calling LLM gets a clear signal.

Transport: stdio (subprocess pattern).  Each MCP client launches this
script as a child process and talks JSON-RPC over stdin/stdout.

For Claude Desktop / Cursor / Continue.dev / Cline — see README.md.

Env:
    SCRIPT_LIBRARY_API   base URL of the local rote API
                         (default: http://127.0.0.1:5572)
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

API_BASE = os.environ.get("SCRIPT_LIBRARY_API", "http://127.0.0.1:5572")

# Long-ish timeout because dispatch_to_delegate may forward calls to local
# LLMs that take 10-30s to respond on a 7B model.
HTTP_TIMEOUT = 120.0

mcp = FastMCP(
    name="rote",
    instructions=(
        "Local Rote backend at "
        f"{API_BASE}. Discover reusable scripts before writing new shell. "
        "Defer mechanical work to registered local delegates (Ollama, sglang, "
        "MetaMCP on edge-host). Never write secret values directly — use "
        "vault_inject so bytes stay server-side."
    ),
)


# ---------------------------------------------------------------------------
# Helper: synchronous HTTP wrapper.  FastMCP tools can be sync or async; we
# choose sync because the local API is fast and httpx.Client is simpler than
# AsyncClient with a shared session.
# ---------------------------------------------------------------------------
def _api(method: str, path: str, **kwargs: Any) -> Any:
    """Call the local Rote HTTP API.  Returns parsed JSON or
    raises a RuntimeError with the API's error message attached."""
    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        try:
            r = client.request(method, f"{API_BASE}{path}", **kwargs)
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"rote API at {API_BASE} not reachable: {exc}. "
                "Run ~/.claude/rote/server/start.sh to bring it up."
            ) from exc
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail", r.text)
            except Exception:
                detail = r.text
            raise RuntimeError(f"{method} {path} → {r.status_code}: {detail}")
        if not r.content:
            return None
        return r.json()


# ---------------------------------------------------------------------------
# Script discovery + execution
# ---------------------------------------------------------------------------
@mcp.tool()
def find_script(query: str, limit: int = 5) -> str:
    """Semantic-search reusable scripts by purpose / when-to-use.

    Use this BEFORE writing a new shell script for a recurring operation.
    Returns a ranked list of matches; if the top match's distance is small
    (< 0.4), prefer running it via run_script over writing new code.

    Args:
        query: free text describing what the script should do
        limit: max matches to return (1-20)
    """
    data = _api("POST", "/scripts/search", json={"query": query, "limit": limit})
    return json.dumps(data, indent=2)


@mcp.tool()
def list_scripts() -> str:
    """List every reusable script with its frontmatter (purpose, when-to-use,
    touches-secrets).  Use list when you want a complete inventory; use
    find_script when you have a target operation in mind."""
    data = _api("GET", "/scripts")
    return json.dumps(data, indent=2)


@mcp.tool()
def show_script(name: str) -> str:
    """Get one script's full frontmatter + path + size.

    Args:
        name: script filename, e.g. "inject-env-secrets.sh"
    """
    data = _api("GET", f"/scripts/{name}")
    return json.dumps(data, indent=2)


@mcp.tool()
def run_script(name: str, args: list[str] | None = None, timeout_seconds: int = 60) -> str:
    """Execute a script from the library and auto-log the outcome.

    The script runs on the same host as the MCP server (because the script
    body lives on disk there).  stdout, stderr, and exit code are returned
    as a JSON envelope.  Args are passed verbatim — quote anything with
    shell metacharacters yourself.

    Every invocation lands in script_run_log so failures + flaky scripts
    surface in the GUI scripts tab and via `show_script` stats.

    Args:
        name: script filename
        args: list of args passed verbatim after the script path
        timeout_seconds: kill the process after this many seconds (default 60)
    """
    import time as _time
    detail = _api("GET", f"/scripts/{name}")
    path = detail.get("path")
    if not path or not Path(path).is_file():
        raise RuntimeError(f"script {name} resolved to missing path: {path}")
    cmd = [path] + list(args or [])
    args_preview = " ".join(map(str, args or []))[:200]
    start = _time.time()
    timed_out = False
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_seconds,
        )
        exit_code = proc.returncode
        stdout, stderr = proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = 124
        stdout = (exc.stdout or b"").decode("utf-8", "replace") if exc.stdout else ""
        stderr = (exc.stderr or b"").decode("utf-8", "replace") if exc.stderr else ""
    duration_ms = int((_time.time() - start) * 1000)

    outcome = (
        "timeout" if timed_out else
        "success" if exit_code == 0 else
        "failure"
    )
    # Log to /scripts/{name}/runs — silent on failure so the real run result
    # isn't masked.
    try:
        _api("POST", f"/scripts/{name}/runs", json={
            "outcome": outcome,
            "exit_code": exit_code,
            "duration_ms": duration_ms,
            "caller": "mcp",
            "args_preview": args_preview,
        })
    except RuntimeError:
        pass

    return json.dumps({
        "name": name, "cmd": cmd, "exit_code": exit_code,
        "outcome": outcome, "duration_ms": duration_ms,
        "stdout": stdout, "stderr": stderr,
        "timeout": timed_out,
    })


@mcp.tool()
def log_script_run(
    name: str,
    outcome: str,
    exit_code: int | None = None,
    duration_ms: int | None = None,
    args_preview: str = "",
    notes: str = "",
) -> str:
    """Manually record a script-run outcome.  Use this when the LLM ran a
    library script through some other path (raw Bash, ssh-then-bash, etc.)
    and you want stats to stay honest.

    Args:
        name: script filename
        outcome: success | failure | partial | timeout
        exit_code: the actual exit code if known
        duration_ms: wall-clock duration if known
        args_preview: first 200 chars of args used
        notes: free-text
    """
    return json.dumps(_api("POST", f"/scripts/{name}/runs", json={
        "outcome": outcome,
        "exit_code": exit_code,
        "duration_ms": duration_ms,
        "caller": "manual",
        "args_preview": args_preview,
        "notes": notes,
    }))


@mcp.tool()
def list_script_runs(name: str, limit: int = 25) -> str:
    """List the recent run-log entries for one script.  Use for audit /
    debugging when a script is failing — see latest outcomes + exit codes.

    Args:
        name: script filename
        limit: max events (1-500)
    """
    return json.dumps(_api("GET", f"/scripts/{name}/runs", params={"limit": limit}), indent=2)


# ---------------------------------------------------------------------------
# Vault (NAMES only — values never leave the server process)
# ---------------------------------------------------------------------------
@mcp.tool()
def vault_keys() -> str:
    """List the NAMES + byte sizes of secrets in the local vault.

    This endpoint will NEVER return secret values, regardless of how the
    request is phrased.  If you need a value to flow into a file, use
    vault_inject instead — the bytes stay server-side."""
    data = _api("GET", "/vault/keys")
    return json.dumps(data, indent=2)


@mcp.tool()
def vault_has(keys: list[str]) -> str:
    """Check which of the given keys exist in the vault.

    Use this before vault_inject so you can give the user a precise
    "missing keys, please add to vault" message instead of failing late.

    Args:
        keys: list of vault key names to check
    """
    data = _api("POST", "/vault/has", json={"keys": keys})
    return json.dumps(data, indent=2)


@mcp.tool()
def vault_inject(
    env_file: str,
    keys: list[str],
    block_label: str = "vault-inject",
) -> str:
    """Inject named vault secrets into a target .env file inside a labeled,
    idempotent block.  Replaces any existing block with the same label.

    The LLM passes key NAMES; the server reads VALUES and writes them.
    Response reports byte counts only — never values.

    Args:
        env_file: absolute path to the target .env (created if missing)
        keys: list of vault key NAMES to inject
        block_label: unique label so re-runs are no-ops; multiple labels
                     can coexist in one .env
    """
    data = _api(
        "POST",
        "/vault/inject",
        json={"env_file": env_file, "keys": keys, "block_label": block_label},
    )
    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# Anti-patterns
# ---------------------------------------------------------------------------
@mcp.tool()
def list_anti_patterns() -> str:
    """List all catalogued anti-patterns, ordered by hit count.

    Use this when closing out a session: scan for patterns that bit the
    work, and bump hit counts via add_anti_pattern (slug match = upsert)."""
    data = _api("GET", "/anti-patterns")
    return json.dumps(data, indent=2)


@mcp.tool()
def find_anti_pattern(query: str, limit: int = 5) -> str:
    """Semantic-search anti-patterns by symptom.

    Use BEFORE a multi-step operation that smells like something past
    sessions hit — search the symptom in your own words.

    Args:
        query: symptom description in free text
        limit: max results
    """
    data = _api("POST", "/anti-patterns/search", json={"query": query, "limit": limit})
    return json.dumps(data, indent=2)


@mcp.tool()
def add_anti_pattern(
    slug: str,
    title: str,
    symptom: str,
    remedy: str,
    token_cost: str | None = None,
) -> str:
    """Insert a new anti-pattern or bump hit_count of an existing slug.

    Slug is the dedupe key; re-recording the same slug bumps hit_count and
    refreshes embedding from the (title + symptom + remedy) blob.

    Args:
        slug: kebab-case identifier
        title: one-line headline
        symptom: what it looks like when you hit it
        remedy: the right pattern to use instead
        token_cost: free-text estimate of the cost when this pattern bites
    """
    body = {"slug": slug, "title": title, "symptom": symptom, "remedy": remedy}
    if token_cost is not None:
        body["token_cost"] = token_cost
    data = _api("POST", "/anti-patterns", json=body)
    return json.dumps(data)


# ---------------------------------------------------------------------------
# Delegates (defer mechanical work)
# ---------------------------------------------------------------------------
@mcp.tool()
def list_design_patterns(category: str | None = None) -> str:
    """List catalogued design patterns ordered by category + name.

    Use this when you're about to design a class hierarchy, service layer,
    resilience layer, or AI-augmented feature.  The catalog encodes proven
    patterns so the LLM doesn't reinvent from mediocre training-data code.

    Args:
        category: optional filter — classical | architectural | resilience |
                  offline | ai
    """
    params = {"category": category} if category else {}
    return json.dumps(_api("GET", "/design-patterns", params=params), indent=2)


@mcp.tool()
def find_design_pattern(query: str, limit: int = 5, category: str | None = None) -> str:
    """Semantic-search the design pattern catalog.

    Use BEFORE writing a new class hierarchy / service / resilience policy /
    AI feature.  Top match's intent + when-to-use + structure + example
    teach the LLM the canonical shape instead of regenerating from training
    data.

    Args:
        query: free-text problem description ("how to swap algorithm at
               runtime", "safe retry of remote calls", "offline-survivable
               event publication")
        limit: max matches (1-50)
        category: optional filter
    """
    body: dict[str, Any] = {"query": query, "limit": limit}
    if category:
        body["category"] = category
    return json.dumps(_api("POST", "/design-patterns/search", json=body), indent=2)


@mcp.tool()
def show_design_pattern(slug: str) -> str:
    """Get one design pattern's full record: intent, when-to-use,
    when-NOT-to-use, structure, example code, relationships."""
    return json.dumps(_api("GET", f"/design-patterns/{slug}"), indent=2)


@mcp.tool()
def log_design_pattern_use(slug: str, notes: str = "") -> str:
    """Bump use_count when you actually applied this pattern in code (not
    just consulted it).  Tracks which patterns are load-bearing."""
    return json.dumps(_api("POST", f"/design-patterns/{slug}/use",
                           params={"notes": notes}))


@mcp.tool()
def list_technologies(category: str | None = None, tag: str | None = None) -> str:
    """List catalogued technologies (concrete tools + their pattern bindings).

    Each entry says which design patterns the tech implements, when to use,
    when NOT (offline-incompat, cloud-lock, scale ceilings), and what to
    use instead.  Tags include: offline-capable, self-hosted, cloud-only,
    vendor-locked, open-source.

    Args:
        category: messaging | realtime | resilience-library |
                  ai-infrastructure | database | identity | mcp-infrastructure |
                  orchestration | vector-db
        tag: filter to entries that carry this tag
    """
    params: dict[str, Any] = {}
    if category: params["category"] = category
    if tag: params["tag"] = tag
    return json.dumps(_api("GET", "/technologies", params=params), indent=2)


@mcp.tool()
def find_technology(query: str, limit: int = 5, category: str | None = None) -> str:
    """Semantic-search the technology catalog.

    Use to answer "what tech implements pattern X given my constraints"
    or "what should I NOT use here and why."  Pairs with find_design_pattern.

    Args:
        query: free-text ("pub/sub broker that works offline", "rate limiting
               that survives offline", "OIDC provider I can self-host")
        limit: max matches
        category: optional filter
    """
    body: dict[str, Any] = {"query": query, "limit": limit}
    if category:
        body["category"] = category
    return json.dumps(_api("POST", "/technologies/search", json=body), indent=2)


@mcp.tool()
def show_technology(slug: str) -> str:
    """Get one technology's full record: name, category, implements_patterns,
    when_to_use, when_not_to_use, limitations, cost, alternatives, tags."""
    return json.dumps(_api("GET", f"/technologies/{slug}"), indent=2)


@mcp.tool()
def log_technology_use(slug: str, notes: str = "") -> str:
    """Bump use_count when you actually selected this technology for an
    implementation."""
    return json.dumps(_api("POST", f"/technologies/{slug}/use",
                           params={"notes": notes}))


@mcp.tool()
def list_commands(family: str | None = None, platform: str | None = None) -> str:
    """List catalogued console commands.  Building-block invocations
    (apt-get, docker, git, find, rsync, ssh, chmod, systemd, openssl, jq)
    with gotchas + cross-platform equivalents.

    Args:
        family: package-mgmt | container | git | fs | net-ssh | perms |
                systemd | monitoring | certs | text | process
        platform: debian | ubuntu | macos | windows | cross-platform | ...
    """
    params: dict[str, Any] = {}
    if family: params["family"] = family
    if platform: params["platform"] = platform
    return json.dumps(_api("GET", "/commands", params=params), indent=2)


@mcp.tool()
def find_command(query: str, limit: int = 5, family: str | None = None) -> str:
    """Semantic-search the commands catalog.  Use BEFORE wiring a common
    console command into a script — get the canonical invocation + the
    gotchas + cross-platform equivalents.

    Args:
        query: free text ("install a package in a Dockerfile",
               "find the process listening on port X",
               "follow a systemd service's logs")
        limit: max matches
        family: filter
    """
    body: dict[str, Any] = {"query": query, "limit": limit}
    if family:
        body["family"] = family
    return json.dumps(_api("POST", "/commands/search", json=body), indent=2)


@mcp.tool()
def show_command(slug: str) -> str:
    """Get one command's full record: command_line, when-to-use, gotchas,
    flag tour, examples, platform equivalents."""
    return json.dumps(_api("GET", f"/commands/{slug}"), indent=2)


@mcp.tool()
def log_command_use(slug: str, notes: str = "") -> str:
    """Bump use_count when you actually used this command in real work."""
    return json.dumps(_api("POST", f"/commands/{slug}/use", params={"notes": notes}))


@mcp.tool()
def list_snippets(language: str | None = None) -> str:
    """List parameterized code snippets.

    Use BEFORE writing boilerplate (FastAPI endpoint, Polly policy
    registration, TanStack mutation, etc.) — return the canonical shape
    instead of regenerating from training data.

    Args:
        language: optional filter — python | csharp | typescript | bash | sql
    """
    params = {"language": language} if language else {}
    return json.dumps(_api("GET", "/snippets", params=params), indent=2)


@mcp.tool()
def find_snippet(query: str, limit: int = 5, language: str | None = None) -> str:
    """Semantic-search the code snippet catalog.

    Args:
        query: free text ("FastAPI semantic search endpoint",
               "Polly retry circuit breaker setup", "React optimistic mutation")
        limit: max matches
        language: optional filter
    """
    body: dict[str, Any] = {"query": query, "limit": limit}
    if language:
        body["language"] = language
    return json.dumps(_api("POST", "/snippets/search", json=body), indent=2)


@mcp.tool()
def show_snippet(slug: str) -> str:
    """Get one snippet's body + placeholders + when-to-use."""
    return json.dumps(_api("GET", f"/snippets/{slug}"), indent=2)


@mcp.tool()
def expand_snippet(slug: str, values: dict[str, str]) -> str:
    """Render a snippet with placeholder substitution.

    Pass a dict mapping placeholder NAME → value.  Tokens in the body that
    look like ${NAME} get replaced.  Response includes the rendered code,
    any placeholders that were left unfilled, and any values that didn't
    match a declared placeholder.

    Args:
        slug: snippet slug
        values: {PLACEHOLDER_NAME: substituted_value}
    """
    return json.dumps(_api("POST", f"/snippets/{slug}/expand", json={"values": values}), indent=2)


@mcp.tool()
def log_snippet_use(slug: str, notes: str = "") -> str:
    """Bump use_count when you actually applied this snippet in real code."""
    return json.dumps(_api("POST", f"/snippets/{slug}/use", params={"notes": notes}))


@mcp.tool()
def list_stacks(outcome: str | None = None) -> str:
    """List recorded stack experiments — technology combinations that
    have been tried and what came of them.

    Args:
        outcome: optional — success | partial | failure | mixed
    """
    params = {"outcome": outcome} if outcome else {}
    return json.dumps(_api("GET", "/stacks", params=params), indent=2)


@mcp.tool()
def find_stack(query: str, limit: int = 5, outcome: str | None = None) -> str:
    """Semantic-search the stack records.

    Use BEFORE picking a technology combination — see if we've tried it
    and what came of it.

    Args:
        query: free text ("offline-capable broker for IoT",
               "sentence-transformers on Windows filesystem",
               "should we use Azure Service Bus")
        limit: max matches
        outcome: filter by outcome
    """
    body: dict[str, Any] = {"query": query, "limit": limit}
    if outcome:
        body["outcome"] = outcome
    return json.dumps(_api("POST", "/stacks/search", json=body), indent=2)


@mcp.tool()
def show_stack(slug: str) -> str:
    """Get one stack record's full content."""
    return json.dumps(_api("GET", f"/stacks/{slug}"), indent=2)


@mcp.tool()
def log_stack_use(slug: str, notes: str = "") -> str:
    """Bump use_count when this stack record informed a real decision."""
    return json.dumps(_api("POST", f"/stacks/{slug}/use", params={"notes": notes}))


@mcp.tool()
def list_delegates() -> str:
    """List every registered local delegate (LLMs, MCP servers, SSH hosts)
    with per-capability success-rate stats from the delegation log.

    Use when planning a multi-step task to see what mechanical work could
    be deferred."""
    data = _api("GET", "/delegates")
    return json.dumps(data, indent=2)


@mcp.tool()
def best_delegate(
    capability: str,
    min_attempts: int = 0,
    min_success_rate: float = 0.0,
) -> str:
    """Pick the best enabled delegate for a capability.

    Returns the highest-success-rate delegate that meets the floor on
    attempts.  Returns null if no qualified delegate exists, signalling
    "do it in-LLM instead."

    Args:
        capability: tag from the taxonomy (bulk-summarization, log-skim,
                    doc-skim, yes-no-classification, code-snippet-extraction,
                    embedding, mcp-tool-aggregation, structured-output, …)
        min_attempts: require this many prior attempts before trusting stats
        min_success_rate: require this rate (0.0-1.0) — defaults to 0
    """
    params = {
        "capability": capability,
        "min_attempts": min_attempts,
        "min_success_rate": min_success_rate,
    }
    data = _api("GET", "/delegates/best", params=params)
    return json.dumps(data, indent=2)


@mcp.tool()
def show_delegate(name: str) -> str:
    """Get one delegate's full record: contact, capabilities, per-capability
    stats, recent 25 log entries.

    Args:
        name: delegate row name (e.g. "local-llm")
    """
    data = _api("GET", f"/delegates/{name}")
    return json.dumps(data, indent=2)


@mcp.tool()
def dispatch_to_delegate(
    delegate: str,
    capability: str,
    prompt: str,
    system: str | None = None,
    schema: dict | None = None,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    task: str | None = None,
    estimated_saved_tokens: int | None = None,
    timeout_seconds: int = 120,
) -> str:
    """Defer work to a delegate.  Routes through the right dispatcher
    script by delegate kind (Ollama / sglang / MetaMCP) — see
    /path/to/rote/scripts/dispatch-to-*.sh.

    Logs the outcome (success / partial / failure / refused) + latency +
    estimated token savings to delegation_log automatically.  Future calls
    to best_delegate(capability) use these stats to rank.

    For MetaMCP delegates, `prompt` is unused; pass tool args via
    dispatch_mcp_tool instead (separate tool because MCP is RPC-shaped).

    Args:
        delegate: registered delegate name
        capability: capability tag for logging
        prompt: user prompt (LLM delegates)
        system: optional system prompt
        schema: optional JSON Schema for structured output (sglang only)
        temperature: sampling temperature
        max_tokens: max output tokens
        task: short summary recorded in delegation_log
        estimated_saved_tokens: best-effort estimate of Claude tokens NOT spent
        timeout_seconds: kill after N seconds
    """
    detail = _api("GET", f"/delegates/{delegate}")
    kind = detail.get("kind")
    if kind != "llm":
        raise RuntimeError(
            f"dispatch_to_delegate handles llm delegates; {delegate} is kind={kind}. "
            "Use dispatch_mcp_tool for MCP delegates."
        )
    # Disambiguate Ollama vs sglang by delegate name; matches the CLI's
    # behavior so a single dispatch UX stays consistent across MCP, CLI,
    # and bash.
    is_sglang = "sglang" in delegate.lower()
    script = (
        "/path/to/rote/scripts/dispatch-to-sglang.sh"
        if is_sglang
        else "/path/to/rote/scripts/dispatch-to-ollama.sh"
    )
    cmd: list[str] = [
        script,
        "--delegate", delegate,
        "--capability", capability,
        "--prompt", prompt,
        "--temperature", str(temperature),
        "--max-tokens", str(max_tokens),
    ]
    if system:
        cmd += ["--system", system]
    if task:
        cmd += ["--task", task]
    if estimated_saved_tokens is not None:
        cmd += ["--estimated-saved", str(estimated_saved_tokens)]
    if schema is not None:
        if not is_sglang:
            raise RuntimeError("--schema requires an sglang delegate")
        cmd += ["--schema", json.dumps(schema)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
    return json.dumps(
        {
            "delegate": delegate,
            "capability": capability,
            "exit_code": proc.returncode,
            "response": proc.stdout,
            "log_line": proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else None,
            "stderr": proc.stderr,
        }
    )


@mcp.tool()
def dispatch_mcp_tool(
    delegate: str,
    tool_name: str,
    args: dict[str, Any] | None = None,
    endpoint: str = "openwebui-api",
    capability: str = "mcp-tool-aggregation",
    task: str | None = None,
    estimated_saved_tokens: int | None = None,
    timeout_seconds: int = 60,
) -> str:
    """Call an MCP tool through a MetaMCP delegate.

    Args:
        delegate: MCP delegate name (e.g. "metamcp-delegate")
        tool_name: MCP tool to invoke
        args: tool arguments as a dict
        endpoint: MetaMCP endpoint namespace (default "openwebui-api")
        capability: capability tag for logging
        task: short summary recorded in delegation_log
        estimated_saved_tokens: best-effort estimate
        timeout_seconds: kill after N seconds
    """
    cmd = [
        "/path/to/rote/scripts/dispatch-to-metamcp.sh",
        "--delegate", delegate,
        "--endpoint", endpoint,
        "--tool", tool_name,
        "--args", json.dumps(args or {}),
        "--capability", capability,
    ]
    if task:
        cmd += ["--task", task]
    if estimated_saved_tokens is not None:
        cmd += ["--estimated-saved", str(estimated_saved_tokens)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
    return json.dumps(
        {
            "delegate": delegate,
            "tool": tool_name,
            "exit_code": proc.returncode,
            "response": proc.stdout,
            "stderr": proc.stderr,
        }
    )


@mcp.tool()
def log_delegation(
    delegate: str,
    capability: str,
    task_summary: str,
    outcome: str,
    latency_ms: int | None = None,
    token_savings: int | None = None,
    notes: str = "",
) -> str:
    """Record a delegation outcome.  Use this when you dispatched
    out-of-band (e.g. ssh + grep) and want the stats to reflect reality —
    dispatch_to_delegate already logs automatically.

    Args:
        delegate: registered delegate name
        capability: capability tag from the taxonomy
        task_summary: 1-2 sentence description of what was attempted
        outcome: success | partial | failure | refused
        latency_ms: time the call actually took
        token_savings: estimated Claude tokens NOT spent
        notes: free-text
    """
    body = {
        "delegate": delegate,
        "capability": capability,
        "task_summary": task_summary,
        "outcome": outcome,
        "latency_ms": latency_ms,
        "token_savings": token_savings,
        "notes": notes,
    }
    data = _api("POST", "/delegations", json=body)
    return json.dumps(data)


@mcp.tool()
def add_delegate(
    name: str,
    kind: str,
    contact: dict,
    capabilities: list[str],
    notes: str = "",
    enabled: bool = True,
) -> str:
    """Register a new local resource Claude can defer to.

    Args:
        name: unique short name
        kind: llm | mcp | tool | host | other
        contact: {protocol, url, ssh?, auth_header?, extra?}
        capabilities: list of capability tags (see best_delegate docs)
        notes: free-text — context, quirks, auth method, model details
        enabled: false to register but not surface in best()
    """
    body = {
        "name": name,
        "kind": kind,
        "contact": contact,
        "capabilities": capabilities,
        "notes": notes,
        "enabled": enabled,
    }
    data = _api("POST", "/delegates", json=body)
    return json.dumps(data)


# ---------------------------------------------------------------------------
# Audit + health (read-only diagnostics)
# ---------------------------------------------------------------------------
@mcp.tool()
def healthz() -> str:
    """Health check of the underlying Rote API.

    Useful for diagnosing 'is the backend up' when a tool call fails."""
    data = _api("GET", "/healthz")
    return json.dumps(data, indent=2)


@mcp.tool()
def recent_audit(limit: int = 50) -> str:
    """Recent audit events from the Rote backend.

    Payloads carry key NAMES + counts only — never secret bytes.  Useful
    for verifying recent vault touches when you suspect a misconfig.

    Args:
        limit: max events (1-500)
    """
    data = _api("GET", "/audit", params={"limit": limit})
    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run()
