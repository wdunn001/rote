# Rote codec-web example

A runnable demonstration of Rote as the **local switchboard** in front of a cloud coordinator, the division of labor argued for in The Mild Take's writing on the codec web. The cloud's job shrinks from metering every word to coordinating a few; the expensive, repetitive, latency-tolerant bulk runs on hardware you own.

```bash
./run-codec-web-demo.sh
```

It runs with no arguments. If a Rote server (`127.0.0.1:5572`) and a local delegate are reachable, it uses them; otherwise it simulates the dispatch so the demo always runs. **It never sends a secret anywhere.**

## What it shows, and where each idea comes from

### 1. A doomed-prompt pre-check, run locally

`scripts/doomed-prompt-precheck.sh` is a deterministic screen that rejects prompts a remote call would waste money on: empty, oversized (context overflow), secret-bearing, or denylisted. This is the edge-side **safety and format pre-check** from [*The envelope tax*](https://themildtake.com/articles/2026-05-18-the-envelope-tax/), which observed that a token-native client can run a local pre-check and catch a meaningful fraction of doomed prompts before they ever leave the machine. Every prompt caught here is a remote round-trip not paid for.

It is also a small proof of Rote's whole thesis: the pre-check is a deterministic tool the agent **recalls and runs** instead of re-implementing a safety check from scratch on every pipeline. A skill that says "validate the prompt first" is a wish; this script is a guarantee.

### 2. Client-side vault inject

When a surviving task needs a secret (an API token to read the record it is classifying), the demo injects that secret from the **local vault** into a local tool call and sends the remote model a prompt that references the secret **by name only**. The byte value never enters the prompt, never crosses the network, never reaches the remote model. The pre-check treats a raw secret in a prompt as *doomed* for exactly this reason.

This is the secret-handling discipline ([`secret-handling` skill](../../claude-code-skills/secret-handling/SKILL.md), [`secret-vault/`](../../secret-vault/)) applied to the edge: in [*The Stenographic Mediator*](https://themildtake.com/articles/2026-06-05-the-stenographic-mediator/), the work that comes off the cloud is the bulk that can run on hardware an organization owns. Secret handling is part of that bulk. The dictionary lookups, conversions, and safety pre-checks a cloud used to perform happen on the edge device that is already there.

### 3. Delegate dispatch to compute you own

The prompts that pass the screen are dispatched to a **delegate**, a piece of compute you own (a local LLM via `scripts/dispatch-to-ollama.sh`), and the outcome plus an estimated token saving is logged to `/delegations`. The delegate is the concrete instance of "the expensive, repetitive bulk run on hardware an organization owns" from the mediator piece. The local-hardware wave that makes this practical, capable models on a desk instead of a per-token bill, is the subject of [*Arming both sides*](https://themildtake.com/articles/2026-06-04-arming-both-sides-nvidia/); the reason not to bet on the metered cloud getting cheaper is [*Five Siphons*](https://themildtake.com/analysis/2026-06-02-five-siphons-ai-infrastructure-wealth-transfer/).

## Trying it with real compute

```bash
# 1. Start Rote
../../server/start.sh                       # binds 127.0.0.1:5572

# 2. Register a local LLM you own as a delegate
curl -s http://127.0.0.1:5572/delegates -H 'content-type: application/json' \
  -d '{"name":"local-llm","kind":"llm",
       "contact":{"protocol":"openai-compatible","url":"http://localhost:11434/v1"},
       "capabilities":["bulk-summarization","log-skim","doc-skim"],"enabled":true}'

# 3. (optional) Add a secret so the vault step is real, not simulated
#    Put SERVICE_BEARER_TOKEN in secret-vault/secrets.json

# 4. Run it
./run-codec-web-demo.sh
```

The point is not the demo's specific numbers. It is the shape: a deterministic, local screen in front of a metered remote, so the remote only ever pays for work that can actually succeed, and never sees a secret.
