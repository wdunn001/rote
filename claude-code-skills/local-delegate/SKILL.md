---
name: local-delegate
description: Use this when you're about to do bulk token work — summarization, log-skimming, doc reading, classification, embedding generation, or any operation whose answer doesn't require Claude's reasoning. Check the Rote delegate registry FIRST (`rote delegate best <capability>`) and defer to a known-capable local resource (local LLM on the .88 box, MetaMCP server, SSH-reachable compute) instead of doing it in-Claude. Always LOG the outcome so future-Claude can decide if this delegate is worth using for this capability.
---

# Local Delegate — Defer + Track Skill

There is a local registry of non-Claude compute resources at `/path/to/rote/` (the same backend as [[rote]]). Each `delegate` row says: how to reach it, what it claims to do, what it has actually succeeded at. Before doing expensive work in Claude's own context, check whether a delegate has a proven track record on this capability and defer to it if so.

## When to invoke

- About to read >5 KB of logs to summarize a pattern
- About to skim a long document for one specific fact
- About to classify many short items (yes/no, spam/not-spam, severity buckets)
- About to compute embeddings for a batch of strings
- About to invoke an MCP tool that the local MetaMCP server proxies
- About to do any operation whose value-add is mechanical rather than reasoning

## When NOT to invoke

- The operation needs Claude's reasoning, judgment, or writing voice (code review, architectural decisions, prose drafts the user reads)
- The operation needs the conversation context (the local delegate doesn't have it)
- Latency matters more than tokens (delegate hop = ~hundreds of ms)
- No qualified delegate exists (`rote delegate best <cap>` returns "no qualified delegate")

## Decision flow

```
about to do bulk work?
├── rote delegate best <capability>
│   ├── returns a delegate with success_rate ≥ 0.7 over ≥ 3 attempts  → defer
│   ├── returns a delegate with low success-rate or few attempts       → think before deferring
│   │                                                                     (cost of a failed defer > cost of doing it)
│   └── no qualified delegate                                          → do in-Claude
└── after the operation (whether you deferred or not):
    rote delegate log <name> <cap> <outcome> --task "<summary>"
                                                    [--latency-ms N] [--saved N]
    so future-Claude has better data
```

## Capabilities taxonomy

These are the names to use when calling `rote delegate best <capability>` and `... log <name> <capability> ...`. Stick to this list so stats aggregate cleanly across sessions.

| Capability                  | What it means                                              |
|---|---|
| `bulk-summarization`        | Reduce a 5+ KB blob to a 1-2 paragraph summary             |
| `log-skim`                  | Find specific lines / patterns in a log file               |
| `doc-skim`                  | Find one fact in a long markdown / code doc                |
| `yes-no-classification`     | Boolean / categorical labeling of short items              |
| `code-snippet-extraction`   | Pull a function / block out of a larger file by signature  |
| `embedding`                 | Compute vector embeddings for a batch                      |
| `mcp-tool-aggregation`      | Discover + dispatch to a downstream MCP tool via MetaMCP   |
| `remote-mcp-proxy`          | Forward a specific MCP call through a relay                |
| `shell-exec-bulk`           | Run a shell pipeline on remote compute (SSH delegate)      |
| `transcoding`               | Audio/video transcode (where remote box has GPU/codecs)    |

If you're about to do something not on this list, **add the capability to the relevant delegate's `capabilities`** AND log the outcome — that's how the taxonomy grows.

## API surface

Token-efficient via CLI; everything is also available over HTTP at `127.0.0.1:5572`.

### Discovery

```bash
rote delegate list
# name <TAB> kind <TAB> enabled <TAB> capabilities=<rate>%/<n>

rote delegate show local-llm
# full detail + recent log + per-capability stats
```

### Picking a delegate

```bash
rote delegate best log-skim
# emits the best qualified delegate; exit 4 if none → do in-Claude
```

`best` filters to `enabled=true` delegates that advertise the capability. By default ranks on observed success-rate; pass `?min_attempts=3&min_success_rate=0.7` to require proof.

### Dispatching (how to actually call the delegate)

The registry does NOT proxy the call for you. It tells you HOW to call it (contact details), you make the call, then you log the outcome.

```bash
contact=$(rote delegate show local-llm | grep '^contact:' | cut -f2)
# parse contact JSON: {"url":"http://edge-host:11434/v1","protocol":"openai-compatible",...}
# call delegate; capture latency

rote delegate log local-llm log-skim success \
    --task "skimmed 20KB nginx errors for 'upstream timed out'" \
    --latency-ms 850 \
    --saved 8000
```

For SSH-style delegates:

```bash
ssh user@edge-host 'grep "ERROR" /var/log/foo.log | tail -50'
# then log
rote delegate log edge-host-ssh-host shell-exec-bulk success \
    --task "grep ERROR /var/log/foo.log tail 50" \
    --latency-ms 120
```

### Recording outcomes (mandatory)

EVERY delegation gets logged — success or failure. Even refusals (delegate up but returned "I don't know" / blocked content). The stats are only useful if they're honest.

- `success` — delegate produced a usable answer; you used it
- `partial` — delegate produced something useful but you had to follow up in-Claude
- `failure` — delegate gave a wrong answer, hallucinated, or returned garbage
- `refused` — delegate refused, errored, or timed out

Be honest about `failure` — that's exactly the data future-Claude needs to STOP deferring this capability.

## Adding a new delegate

```bash
# JSON via curl (CLI has no add subcommand yet):
curl -X POST -H 'content-type: application/json' http://127.0.0.1:5572/delegates -d '{
  "name": "edge-host-llama-13b",
  "kind": "llm",
  "contact": {
    "protocol": "openai-compatible",
    "url": "http://edge-host:11434/v1",
    "ssh": {"user": "edge-host", "host": "edge-host"}
  },
  "capabilities": ["bulk-summarization", "log-skim"],
  "notes": "Llama 3 13B via Ollama on edge-host. Auth: none. Context: 8K.",
  "enabled": true
}'
```

## Updating endpoint after first probe

The seeded delegates (`local-llm`, `metamcp-delegate`) start with placeholder URLs and `enabled=false`. Once you've confirmed the endpoint:

```bash
rote delegate set-url local-llm http://edge-host:11434/v1
rote delegate enable local-llm
```

## Cross-reference

- [[rote]] — sibling skill for reusable scripts
- [[secret-handling]] — if a delegate needs a credential, ALWAYS via vault, never inline
- See anti-pattern `delegate-not-consulted` for the failure mode this skill prevents
- See `/path/to/rote/server/README.md` for the full API surface

## Evolution

This skill is at `~/.claude/skills/local-delegate/SKILL.md`. Iterate by editing. Common changes that may want to land:
- New capability tags as the work surfaces them
- Per-delegate notes that document quirks (context window limits, prompt-injection-prone formats, etc.)
- Default `min_attempts` / `min_success_rate` for `best` if defaults turn out wrong
