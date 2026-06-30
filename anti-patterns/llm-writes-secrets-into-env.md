---
slug: llm-writes-secrets-into-env
title: LLM writes private keys / API secrets into .env via Write tool
hit_count: 3
token_cost: high — secrets enter LLM context, get logged in transcripts, may end up in training/reasoning traces
---

# Symptom

User asks "set up .env with the dev credentials". Claude reads a vault, reads a key value, then uses Edit/Write to embed the value literally into a `.env` file. The secret bytes pass through Claude's reasoning context and get written into the conversation transcript.

# Root cause

There is no enforced separation between "Claude knows which key to inject" and "Claude knows the key's value". Both flow through the same context. As soon as a secret value is in the assistant message stream, it's persisted in the transcript directory, may be cached, and is not safely revocable.

# Remedy

Use the rote `inject-env-secrets.sh` script. It calls the local API's `POST /vault/inject` endpoint, which:

1. Reads the named secrets from `/path/to/rote/secret-vault/secrets.json` server-side
2. Writes them directly into the target `.env` inside an idempotent block label
3. Returns to Claude only key NAMES + byte counts — never values

```bash
/path/to/rote/scripts/inject-env-secrets.sh \
    --env-file /path/to/.env \
    --key DATABASE_PASSWORD \
    --key STRIPE_SECRET_KEY \
    --label "deploy-secrets"
```

Or via CLI:

```bash
rote vault inject \
    --env-file /path/to/.env \
    --key DATABASE_PASSWORD \
    --key STRIPE_SECRET_KEY \
    --label deploy-secrets
```

# Detection

Anytime Claude is about to write a `.env` file with literal secret values, that's the smell. The fix is to add the secret to the local vault (a human action) and then have Claude call `inject-env-secrets.sh` with the key NAME.

# See also

- `/path/to/rote/secret-vault/README.md`
- [[feedback-no-secrets-in-llm-context]]
