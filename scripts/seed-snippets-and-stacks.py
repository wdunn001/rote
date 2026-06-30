#!/usr/bin/env python3
"""
script: seed-snippets-and-stacks.py
purpose: Generate the curated initial markdown for the snippets and stacks
         catalogs.  Idempotent — only writes when content changed.
family: seed-snippets-and-stacks
environment: cross-python
inputs:  --root <path>   default /path/to/rote/
         --dry-run       print what would be written
outputs: per-file lines
exit 0 success, 5 bad args
added: 2026-06-03
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# SNIPPETS
# ---------------------------------------------------------------------------
SNIPPETS: list[dict] = [
    {
        "slug": "fastapi-list-endpoint-with-stats",
        "name": "FastAPI list endpoint with optional stats join",
        "language": "python",
        "applies_patterns": "repository-pattern, service-layer",
        "applies_technologies": "sqlite, postgresql",
        "when_to_use": """
Adding a list endpoint to FastAPI where each entry should optionally
include aggregate stats joined from a sibling table.  The rote
uses this shape for /scripts, /design-patterns, /technologies, etc.
""",
        "when_not_to_use": """
Pagination is cursor-based instead of offset-based (use the cursor variant).

The aggregate stats are heavy enough they warrant a separate endpoint.
""",
        "placeholders": [
            ("RESOURCE_SINGULAR", "lowercase_snake singular name of the resource", "drone"),
            ("RESOURCE_PLURAL",   "plural form for the response key", "drones"),
            ("ROUTE_PATH",        "URL path under root", "/drones"),
            ("PRIMARY_TABLE",     "main table name", "drones"),
            ("OPERATION_ID",      "stable operation id for OpenAPI", "list_drones"),
        ],
        "snippet": """\
@app.get("${ROUTE_PATH}", operation_id="${OPERATION_ID}")
def list_${RESOURCE_PLURAL}(include_stats: bool = True) -> dict[str, Any]:
    \"\"\"List ${RESOURCE_PLURAL} with optional aggregate stats joined per row.\"\"\"
    out = []
    with _conn() as c:
        for row in c.execute("SELECT * FROM ${PRIMARY_TABLE} ORDER BY name"):
            entry = _serialize_${RESOURCE_SINGULAR}(row)
            if include_stats:
                entry["stats"] = _${RESOURCE_SINGULAR}_stats(c, entry["id"])
            out.append(entry)
    return {"${RESOURCE_PLURAL}": out, "count": len(out)}""",
        "example_expansion": "See /scripts and /delegates in the live FastAPI server.",
    },
    {
        "slug": "fastapi-semantic-search-endpoint",
        "name": "FastAPI sqlite-vec semantic-search endpoint",
        "language": "python",
        "applies_patterns": "semantic-search-with-embeddings, rag-retrieval-augmented-generation",
        "applies_technologies": "sqlite, sqlite-vec",
        "when_to_use": """
Adding semantic search over a small-to-medium corpus indexed in sqlite-vec.
The rote uses this shape for /scripts/search, /anti-patterns/search,
/design-patterns/search, /technologies/search.
""",
        "when_not_to_use": """
Corpus > 1M rows — use a dedicated vector DB (Qdrant, Milvus).

You need hybrid search (BM25 + vector) — sqlite-vec doesn't ship it built-in.
""",
        "placeholders": [
            ("RESOURCE",        "snake_case resource name", "anti_patterns"),
            ("VEC_TABLE",       "sqlite-vec virtual table name", "anti_patterns_vec"),
            ("ROUTE_PATH",      "URL path", "/anti-patterns/search"),
            ("OPERATION_ID",    "OpenAPI op id", "search_anti_patterns"),
            ("SELECT_COLS",     "columns to return alongside distance", "slug, title, symptom"),
        ],
        "snippet": """\
class ${RESOURCE_PASCAL}SearchRequest(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=50)


@app.post("${ROUTE_PATH}", operation_id="${OPERATION_ID}")
def search_${RESOURCE}(req: ${RESOURCE_PASCAL}SearchRequest) -> dict[str, Any]:
    \"\"\"Semantic similarity search over ${RESOURCE}.\"\"\"
    _sync_${RESOURCE}()
    q = _embed(req.query)
    with _conn() as c:
        rows = list(c.execute(
            f\"\"\"
            SELECT ${SELECT_COLS}, ${VEC_TABLE}.distance
            FROM ${VEC_TABLE}
            JOIN ${RESOURCE} ON ${RESOURCE}.rowid = ${VEC_TABLE}.rowid
            WHERE ${VEC_TABLE}.embedding MATCH ? AND k = ?
            ORDER BY ${VEC_TABLE}.distance
            \"\"\",
            (q, req.limit),
        ))
    return {"query": req.query, "matches": [_row_to_match(r) for r in rows]}""",
        "example_expansion": "See search_anti_patterns / search_design_patterns in server/app.py.",
    },
    {
        "slug": "polly-named-policy-registration",
        "name": "Polly named-policy registration",
        "language": "csharp",
        "applies_patterns": "circuit-breaker, retry-with-exponential-backoff-jitter, timeout-and-deadline, bulkhead",
        "applies_technologies": "polly",
        "when_to_use": """
Every outbound HttpClient in a .NET app needs a named Polly policy.  This
snippet registers a typed HttpClient + a composed policy stack:
timeout(individual) → retry → circuit-breaker → bulkhead.
""",
        "when_not_to_use": """
You're using Microsoft.Extensions.Http.Resilience (.NET 8+) — has a more
modern API and is the recommended replacement.

You're using HttpClientFactory's basic resilience — Polly composition gives
you more control.
""",
        "placeholders": [
            ("CLIENT_INTERFACE", "the IFooClient interface name", "IGraphEmailClient"),
            ("CLIENT_TYPE",      "the concrete implementation type", "GraphEmailClient"),
            ("POLICY_NAME",      "kebab-case named policy for the registry", "graph-email"),
            ("BASE_ADDRESS",     "the upstream base URL", "https://graph.microsoft.com"),
            ("RETRY_COUNT",      "max retries before giving up", "4"),
            ("BREAKER_THRESHOLD", "consecutive failures before breaker opens", "5"),
            ("BREAKER_DURATION_SEC", "circuit-breaker cooldown seconds", "30"),
            ("MAX_PARALLELIZATION", "bulkhead concurrency cap", "10"),
            ("TIMEOUT_SEC",      "per-attempt timeout seconds", "15"),
        ],
        "snippet": """\
// ${POLICY_NAME} — outbound calls to ${BASE_ADDRESS}
services.AddHttpClient<${CLIENT_INTERFACE}, ${CLIENT_TYPE}>(c =>
    {
        c.BaseAddress = new Uri("${BASE_ADDRESS}");
    })
    .AddPolicyHandler(Policy<HttpResponseMessage>
        .Handle<HttpRequestException>()
        .OrResult(r => (int)r.StatusCode >= 500)
        .WaitAndRetryAsync(${RETRY_COUNT}, attempt =>
            TimeSpan.FromMilliseconds(Math.Min(60_000,
                200 * Math.Pow(2, attempt) + Random.Shared.Next(0, 250)))))
    .AddPolicyHandler(Policy<HttpResponseMessage>
        .Handle<HttpRequestException>()
        .CircuitBreakerAsync(${BREAKER_THRESHOLD}, TimeSpan.FromSeconds(${BREAKER_DURATION_SEC})))
    .AddPolicyHandler(Policy.TimeoutAsync<HttpResponseMessage>(${TIMEOUT_SEC}))
    .AddPolicyHandler(Policy.BulkheadAsync<HttpResponseMessage>(
        maxParallelization: ${MAX_PARALLELIZATION}, maxQueuingActions: 50));""",
        "example_expansion": "graph-email, authentik, mqtt-publish in Acme.  See CLAUDE.md 'Polly named-policy convention'.",
    },
    {
        "slug": "aspnet-controller-with-policy",
        "name": "ASP.NET controller with permission policy",
        "language": "csharp",
        "applies_patterns": "service-layer",
        "applies_technologies": "",
        "when_to_use": """
New REST endpoint in Acme where authorization is permission-based
(not just authenticated).  Uses the Policy attribute matching
AuthorizationExtensions.Policy enum + delegates to an AppService.
""",
        "when_not_to_use": """
Public endpoint (no auth) — use [AllowAnonymous].

The work belongs in the Worker (queued) — controller should enqueue, not do it.
""",
        "placeholders": [
            ("CONTROLLER_NAME",  "controller class name", "DroneCommandsController"),
            ("ROUTE_PREFIX",     "URL prefix", "drones"),
            ("ENDPOINT_NAME",    "action method name", "Issue"),
            ("VERB_PATH",        "URL suffix", "{droneId}/commands"),
            ("HTTP_METHOD",      "HTTP method attribute", "HttpPost"),
            ("POLICY_NAME",      "policy enum value", "DronesControl"),
            ("APP_SERVICE",      "the app service field type", "IDroneCommandAppService"),
            ("APP_SERVICE_VAR",  "the field name", "_droneCommands"),
            ("REQUEST_DTO",      "request body DTO type", "IssueDroneCommandRequest"),
        ],
        "snippet": """\
[ApiController]
[Route("api/v1/${ROUTE_PREFIX}")]
public class ${CONTROLLER_NAME} : ControllerBase {
    private readonly ${APP_SERVICE} ${APP_SERVICE_VAR};
    public ${CONTROLLER_NAME}(${APP_SERVICE} svc) => ${APP_SERVICE_VAR} = svc;

    [${HTTP_METHOD}("${VERB_PATH}")]
    [Authorize(Policy = nameof(AuthorizationExtensions.Policy.${POLICY_NAME}))]
    public async Task<IActionResult> ${ENDPOINT_NAME}(
        [FromRoute] DroneId droneId,
        [FromBody] ${REQUEST_DTO} req,
        CancellationToken ct
    ) {
        var result = await ${APP_SERVICE_VAR}.${ENDPOINT_NAME}Async(droneId, req, ct);
        return result switch {
            { Status: "denied", Reason: var r } => Forbid(r),
            { Status: "accepted" }              => Accepted(result),
            _                                   => BadRequest(result)
        };
    }
}""",
        "example_expansion": "See DroneCommandsController, FleetCommandsController in example-app.",
    },
    {
        "slug": "tanstack-query-optimistic-mutation",
        "name": "TanStack Query mutation with optimistic UI",
        "language": "typescript",
        "applies_patterns": "optimistic-ui",
        "applies_technologies": "",
        "when_to_use": """
Confident user actions (drag, click confirmed button) where immediate
feedback matters.  Rollback on server failure.
""",
        "when_not_to_use": """
Irreversible side effects (sending money, posting public content).

The query is so cheap that just letting it round-trip is fine.
""",
        "placeholders": [
            ("HOOK_NAME",      "name of the React hook", "useIssueCommand"),
            ("QUERY_KEY",      "the query-key tuple", "['drone', droneId]"),
            ("API_CALL",       "the API call expression", "api.issueCommand(droneId, cmd)"),
            ("ARG_TYPE",       "the mutation arg type", "DroneCommand"),
            ("LOCAL_APPLY",    "function that mutates the cached value", "applyOptimistically"),
        ],
        "snippet": """\
export function ${HOOK_NAME}(droneId: DroneId) {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (cmd: ${ARG_TYPE}) => ${API_CALL},
        onMutate: async (cmd) => {
            await qc.cancelQueries({ queryKey: ${QUERY_KEY} });
            const prev = qc.getQueryData(${QUERY_KEY});
            qc.setQueryData(${QUERY_KEY}, (old: any) => ${LOCAL_APPLY}(old, cmd));
            return { prev };
        },
        onError: (_err, _cmd, ctx) => {
            if (ctx?.prev !== undefined) qc.setQueryData(${QUERY_KEY}, ctx.prev);
        },
        onSettled: () => qc.invalidateQueries({ queryKey: ${QUERY_KEY} }),
    });
}""",
        "example_expansion": "See useDroneCommandHub.ts and useFleetCommands.ts in apps/web.",
    },
    {
        "slug": "expo-secure-store-set-and-load",
        "name": "expo-secure-store SET + LOAD pair",
        "language": "typescript",
        "applies_patterns": "secret-handling",
        "applies_technologies": "",
        "when_to_use": """
Persisting device-side secrets in the Acme companion: device cert
private key, OIDC tokens, vault values that must survive app restarts.
""",
        "when_not_to_use": """
Non-sensitive config (AsyncStorage is simpler).

Cross-device sync needed (SecureStore is device-only by design).
""",
        "placeholders": [
            ("KEY_NAME", "the storage key constant", "KEY_DEVICE_PRIVATE_KEY_PEM"),
            ("KEY_DESC", "human-readable description for errors", "device cert private key"),
        ],
        "snippet": """\
import * as SecureStore from 'expo-secure-store';

export const ${KEY_NAME} = '${KEY_NAME}';

export async function set${KEY_NAME}(value: string): Promise<void> {
    try {
        await SecureStore.setItemAsync(${KEY_NAME}, value, {
            keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
        });
    } catch (err) {
        throw new Error(`failed to persist ${KEY_DESC}: ${err}`);
    }
}

export async function load${KEY_NAME}(): Promise<string | null> {
    return SecureStore.getItemAsync(${KEY_NAME});
}""",
        "example_expansion": "See apps/companion/src/identity/deviceCert.ts.",
    },
    {
        "slug": "bash-idempotent-env-block-write",
        "name": "Bash idempotent labeled-block .env writer",
        "language": "bash",
        "applies_patterns": "idempotency-token",
        "applies_technologies": "",
        "when_to_use": """
Append KEY=VALUE lines inside a labeled block in a .env file so the writer
is idempotent — re-running replaces the prior block atomically rather than
duplicating.
""",
        "when_not_to_use": """
Single-key replacement (just sed).

Values contain secrets — use the vault inject API instead.
""",
        "placeholders": [
            ("ENV_FILE",   "absolute path to the .env file", "/srv/app/.env"),
            ("BLOCK_LABEL", "unique label so re-runs replace the same block", "deploy-secrets"),
            ("KEY_VALUES",  "newline-separated KEY=VALUE pairs", "FOO=bar\\nBAZ=qux"),
        ],
        "snippet": """\
# Idempotent labeled-block writer.  Replaces the >>> ${BLOCK_LABEL} >>> block
# atomically; appends a new one if missing.
write_labeled_block() {
    local file="${ENV_FILE}"
    local label="${BLOCK_LABEL}"
    local body="${KEY_VALUES}"
    local tmp; tmp=$(mktemp)
    [[ -f "$file" ]] || touch "$file"
    awk -v label="$label" -v body="$body" '
        BEGIN { in_block=0; printed=0 }
        $0 == "# >>> " label " >>>" { in_block=1; print; print body; print "# <<< " label " <<<"; printed=1; next }
        $0 == "# <<< " label " <<<" { in_block=0; next }
        in_block { next }
        { print }
        END { if (printed==0) { print "# >>> " label " >>>"; print body; print "# <<< " label " <<<" } }
    ' "$file" > "$tmp"
    mv "$tmp" "$file"
}""",
        "example_expansion": "See scripts/inject-env-secrets.sh + the /vault/inject server-side implementation.",
    },
    {
        "slug": "mavlink-discriminated-union-typescript",
        "name": "MAVLink DroneCommand discriminated union (TS)",
        "language": "typescript",
        "applies_patterns": "command, strategy",
        "applies_technologies": "",
        "when_to_use": """
Defining a verb set where each verb has different payload shape and the
encoder/dispatcher needs exhaustive case handling.  Used heavily in
packages/mavlink-control.
""",
        "when_not_to_use": """
All verbs share the same payload shape — use a regular interface + verb enum.

The set is huge (50+ verbs) — consider a class-per-verb design instead.
""",
        "placeholders": [
            ("UNION_NAME", "the discriminated-union type name", "DroneCommand"),
            ("DISCRIM",    "the discriminator field name", "kind"),
        ],
        "snippet": """\
export type ${UNION_NAME} =
    | { ${DISCRIM}: 'arm' }
    | { ${DISCRIM}: 'disarm' }
    | { ${DISCRIM}: 'flyToHere', target: GeoPoint, ned?: NedOffset }
    | { ${DISCRIM}: 'follow', leader: SystemId, distance?: number }
    | { ${DISCRIM}: 'rtl' }
    | { ${DISCRIM}: 'uploadMission', plan: FlightPlan };

export function dispatch${UNION_NAME}(
    cmd: ${UNION_NAME},
    handler: { [K in ${UNION_NAME}[\"${DISCRIM}\"]]: (c: Extract<${UNION_NAME}, { ${DISCRIM}: K }>) => Uint8Array }
): Uint8Array {
    return (handler as any)[cmd.${DISCRIM}](cmd);
}""",
        "example_expansion": "See packages/mavlink-control/src/DroneCommand.ts.",
    },
    {
        "slug": "pydantic-model-with-frontmatter-meta",
        "name": "Pydantic model paired with operation_id-pinned endpoint",
        "language": "python",
        "applies_patterns": "service-layer",
        "applies_technologies": "",
        "when_to_use": """
Adding a request/response model + a typed FastAPI endpoint that takes it
as the body and has a stable operation_id for OpenAPI tool-name stability.
""",
        "when_not_to_use": """
The endpoint takes only path/query params — use Query/Path types directly.
""",
        "placeholders": [
            ("MODEL_NAME",   "Pydantic model class name", "DelegationLogCreate"),
            ("ROUTE_PATH",   "URL path", "/delegations"),
            ("HTTP_METHOD",  "fastapi decorator method", "post"),
            ("OPERATION_ID", "stable op id", "log_delegation"),
            ("FIELDS",       "field block — one per line indented", "delegate: str = Field(...)\\n    capability: str = Field(..., min_length=1)"),
        ],
        "snippet": """\
class ${MODEL_NAME}(BaseModel):
    ${FIELDS}


@app.${HTTP_METHOD}("${ROUTE_PATH}", operation_id="${OPERATION_ID}")
def ${OPERATION_ID}(req: ${MODEL_NAME}) -> dict[str, Any]:
    # TODO: implement
    return {"action": "logged"}""",
        "example_expansion": "See log_delegation, upsert_anti_pattern in server/app.py.",
    },
]


# ---------------------------------------------------------------------------
# STACKS
# ---------------------------------------------------------------------------
STACKS: list[dict] = [
    {
        "slug": "rote-fastapi-sqlite-vec-ollama",
        "name": "FastAPI + SQLite + sqlite-vec + Ollama-embedding (this repo)",
        "technologies": "fastapi, sqlite, sqlite-vec, ollama",
        "patterns": "rag-retrieval-augmented-generation, semantic-search-with-embeddings, repository-pattern, service-layer",
        "context": "wdunn001/rote — local context system, this repo",
        "outcome": "success",
        "what_worked": """
- FastAPI's auto-generated OpenAPI exposed the whole system to MCP + function-calling LLMs with zero extra work
- sqlite-vec at < 1M vectors is plenty fast for semantic search
- Switching from sentence-transformers (80MB torch dep + drvfs install fragility) to Ollama's nomic-embed-text dropped install time from ~5 min to instant
- Same SQLite file holds audit log, anti-patterns, design-patterns, technologies, snippets, stacks, scripts index, delegation log, script run log — one transactional surface for the whole system
- FastMCP wraps the HTTP API as MCP tools without re-implementing anything
""",
        "what_didnt": """
- pip install on drvfs (Windows-mounted /mnt/h/) corrupted the venv repeatedly — moved venv to ~/.cache/ on WSL native
- sentence-transformers + torch installs take 5+ minutes on drvfs and produce zero-byte __init__.py files when interrupted
""",
        "when_to_reuse": """
- Local-first / single-host RAG systems
- Embedded vector search up to ~1M documents
- Any 'one server many client types' shape (MCP + HTTP + GUI from one backend)
""",
        "when_to_avoid": """
- Multi-node distributed deployment (sqlite-vec is single-process)
- Strict horizontal scale (use Qdrant + Postgres pair instead)
""",
        "references": "https://github.com/wdunn001/rote",
    },
    {
        "slug": "acme-saas-core",
        "name": "Acme SaaS core stack",
        "technologies": "postgresql, rabbitmq, mosquitto, authentik, signalr, polly",
        "patterns": "clean-architecture, hexagonal-ports-adapters, repository-pattern, service-layer, circuit-breaker, retry-with-exponential-backoff-jitter, bulkhead, outbox-pattern",
        "context": "example-app — drone fleet SaaS",
        "outcome": "success",
        "what_worked": """
- Clean Architecture boundary (Domain/Application/Infrastructure/Api) survived multiple infra swaps without rewriting business code
- Polly named-policy convention (graph-email, authentik, mqtt-publish, etc.) made resilience auditable
- Mosquitto for the public MQTT surface (DeviceA cellular bridges) + RabbitMQ for the cot-bridge + API exchange — both self-hosted, both offline-survivable
- Authentik OIDC handles SPA + companion + shop + marketing under one IdP
- SignalR /hubs/notifications for realtime decode/analysis progress; falls back through transports automatically
""",
        "what_didnt": """
- N/A at the stack level; this is the canonical stack.  Tactical issues tracked in anti-patterns + chronicles.
""",
        "when_to_reuse": """
- Multi-tenant SaaS with edge/disconnected devices needing offline mode
- Realtime progress + multi-channel notification needs
""",
        "when_to_avoid": """
- Cloud-only deployments where managed alternatives are cheaper (Azure Service Bus / Event Grid / SignalR Service — but those don't work offline)
""",
        "references": "example-app CLAUDE.md",
    },
    {
        "slug": "azure-service-bus-for-offline-considered-and-rejected",
        "name": "Azure Service Bus for an offline-required pipeline (considered, REJECTED)",
        "technologies": "azure-service-bus",
        "patterns": "queue-based-load-leveling, outbox-pattern",
        "context": "Acme — drone telemetry + companion offline queue",
        "outcome": "failure",
        "what_worked": """
- Service Bus is genuinely well-designed for cloud-native queueing
- Managed; you don't operate the broker
- AAD integration is clean
""",
        "what_didnt": """
- Doesn't work offline.  Period.  No on-prem option.  No edge deployment.
- Drones, companion phones in the field, and the GCS bundle MUST work without cloud connectivity — Service Bus is a non-starter
- Cost scales per-message; high-fanout telemetry would be expensive
""",
        "when_to_reuse": """
- Pure cloud-native Azure workloads with NO offline requirement
""",
        "when_to_avoid": """
- ANY Acme use case — devices and the GCS bundle are offline-survivable by design.
- Multi-cloud / vendor-lock-averse architectures.
""",
        "references": "See technology entry: azure-service-bus",
    },
    {
        "slug": "sentence-transformers-on-drvfs-failure",
        "name": "sentence-transformers + torch on Windows drvfs (FAILURE)",
        "technologies": "sentence-transformers, sqlite-vec",
        "patterns": "semantic-search-with-embeddings",
        "context": "rote initial bootstrap on ~/dev/",
        "outcome": "failure",
        "what_worked": """
- The libraries themselves work fine when installed on a native Linux filesystem.
""",
        "what_didnt": """
- pip install of torch + sentence-transformers on drvfs (Windows-mounted /mnt/h/) produced zero-byte __init__.py files in 30% of attempts
- A killed install left site-packages in inconsistent state; even `rm -rf .venv` was slow enough to fail under shell timeouts
- venv resolution kept claiming success while the package was partially installed
""",
        "when_to_reuse": """
- Never reuse this combo on drvfs.  Use Ollama nomic-embed-text as the embedding backend instead — sheds the 80MB torch dep entirely.
""",
        "when_to_avoid": """
- Any pip install of large packages on drvfs filesystems.
- Move venvs to ~/.cache/ on WSL native FS; symlink under the repo so callers see the expected .venv path.
""",
        "references": "scripts/seed-design-patterns-and-technologies.py - see Ollama tech entry",
    },
    {
        "slug": "claude-code-skill-pipeline",
        "name": "Claude Code skills + auto-memory + MCP server (this repo)",
        "technologies": "metamcp",
        "patterns": "skill-based-prompting, rag-retrieval-augmented-generation, mcp-aggregator-proxy, tool-use-function-calling",
        "context": "wdunn001/rote — Claude Code integration",
        "outcome": "success",
        "what_worked": """
- 5 skills under ~/.claude/skills/ + memory entry + MCP server + OpenAPI = ANY LLM client can use the same tools
- Symlinked skills (--mode symlink) flow edits back to the repo for commit
- Bootstrap script (rote bootstrap) sets up backend + MCP + client configs + skills + verify in one command on a fresh machine
- ROADMAP items get auto-recorded as anti-patterns + design patterns get cross-linked to technologies
""",
        "what_didnt": """
- Required a rule-strengthening step to actually change behavior; infrastructure alone wasn't enough
- Initial use_count is always zero — patterns are documented but the LLM has to actively reach for them; needs ongoing reinforcement
""",
        "when_to_reuse": """
- Any LLM-augmented workflow where you want session-persistent knowledge
- When the training data is mediocre on your problem domain (cite a curated catalog instead)
""",
        "when_to_avoid": """
- One-off sessions where the setup cost exceeds the benefit
- When the catalog isn't curated — uncurated catalogs are training-data with extra steps
""",
        "references": "https://github.com/wdunn001/rote",
    },
]


def render_snippet(s: dict) -> str:
    placeholders_md = "\n".join(
        f"- {name}: {desc}" + (f" (example: {ex})" if ex else "")
        for name, desc, ex in s["placeholders"]
    )
    refs = s.get("references", "")
    return (
        "---\n"
        f"slug: {s['slug']}\n"
        f"name: {s['name']}\n"
        f"language: {s['language']}\n"
        f"applies_patterns: {s.get('applies_patterns', '')}\n"
        f"applies_technologies: {s.get('applies_technologies', '')}\n"
        f"references: {refs}\n"
        "---\n\n"
        "# When to use\n"
        f"{s['when_to_use'].strip()}\n\n"
        "# When NOT to use\n"
        f"{s['when_not_to_use'].strip()}\n\n"
        "# Placeholders\n"
        f"{placeholders_md}\n\n"
        "# Snippet\n"
        f"```{s['language']}\n{s['snippet']}\n```\n\n"
        "# Example expansion\n"
        f"{s.get('example_expansion', '').strip()}\n"
    )


def render_stack(s: dict) -> str:
    refs = s.get("references", "")
    return (
        "---\n"
        f"slug: {s['slug']}\n"
        f"name: {s['name']}\n"
        f"technologies: {s['technologies']}\n"
        f"patterns: {s['patterns']}\n"
        f"context: {s['context']}\n"
        f"outcome: {s['outcome']}\n"
        f"references: {refs}\n"
        "---\n\n"
        "# What worked\n"
        f"{s['what_worked'].strip()}\n\n"
        "# What didn't\n"
        f"{s['what_didnt'].strip()}\n\n"
        "# When to reuse\n"
        f"{s['when_to_reuse'].strip()}\n\n"
        "# When to avoid\n"
        f"{s['when_to_avoid'].strip()}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/path/to/rote")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    sn_dir = root / "snippets"
    st_dir = root / "stacks"

    written = 0
    skipped = 0

    for s in SNIPPETS:
        category_dir = sn_dir / s["language"]
        category_dir.mkdir(parents=True, exist_ok=True)
        path = category_dir / f"{s['slug']}.md"
        content = render_snippet(s)
        if path.exists() and path.read_text() == content:
            skipped += 1
            continue
        if args.dry_run:
            print(f"[dry-run] would write {path}")
        else:
            path.write_text(content)
            print(f"+ {path}")
        written += 1

    for s in STACKS:
        # categorize by outcome so the directory tree shows it at a glance
        category_dir = st_dir / s["outcome"]
        category_dir.mkdir(parents=True, exist_ok=True)
        path = category_dir / f"{s['slug']}.md"
        content = render_stack(s)
        if path.exists() and path.read_text() == content:
            skipped += 1
            continue
        if args.dry_run:
            print(f"[dry-run] would write {path}")
        else:
            path.write_text(content)
            print(f"+ {path}")
        written += 1

    print(f"\n{written} written, {skipped} unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
