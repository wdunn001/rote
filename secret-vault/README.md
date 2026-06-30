# Secret Vault

A flat local-only JSON store at `secrets.json` mapping secret IDs to values. **Never committed, never sent to any LLM.**

The whole point: the AI agent learns the **names** of your secrets and can ask the server to inject them where they are needed, but the secret **bytes** never enter the model's context. The server reads `secrets.json`; the model only ever sees key names and byte counts.

## Design

```
secret-vault/
├── README.md             (this file — safe to share)
├── secrets.json          (CONTAINS BYTES — gitignored, never read by the agent)
└── secrets.example.json  (template / shape reference — safe to share)
```

The agent can:

- Read this README and `secrets.example.json` to learn what secret IDs exist (the **names**, not values).
- Invoke `scripts/inject-env-secrets.sh --key <ID>` to write a secret into an env file.
- Confirm a secret exists by checking the OUTPUT of a script run (e.g., a "wrote 3 keys" stdout line).

The agent can **NOT**:

- Read `secrets.json` directly via Read or `cat`. The path is gitignored AND the `secret-handling` skill explicitly blocks reading it. If a session tries, treat that as a security-pattern violation and log it under `anti-patterns/`.
- Echo a secret value to stdout in chat.
- Paste a secret into a git commit, a deploy log shown in chat, or any artifact the user might quote.

## Vault entry format

`secrets.json` is a flat object:

```jsonc
{
  // Plain env-style keys (SCREAMING_SNAKE) hold opaque tokens.
  "OPENAI_API_KEY": "sk-...",
  "GITHUB_TOKEN": "ghp_...",
  "DATABASE_URL": "postgres://user:pass@localhost:5432/app",

  // Multi-line values (PEM, etc.) keep their newlines as \n in JSON;
  // the inject script unescapes them when writing to .env.
  "TLS_PRIVATE_KEY_PEM": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
}
```

Keys are env-style. For .NET configuration you can also use the `Section__Key` double-underscore convention; for plain env use `SCREAMING_SNAKE`. Values are the raw secret bytes.

## How a secret gets into the vault

Human-only operations (the agent never sees the bytes):

1. Copy `secrets.example.json` to `secrets.json`.
2. Add the key.
3. Paste the value (token, base64, hex, PEM, whatever the consumer expects).
4. Save.

## How a script reads a secret

Scripts under `scripts/` that need a secret use `jq` to extract it from `secrets.json`:

```bash
val=$(jq -r --arg k "$key_name" '.[$k]' "$VAULT_PATH")
```

The script then writes the value to wherever the consumer needs it (an `.env` file, a kubectl secret, etc.) WITHOUT ever printing it to stdout. If the script must report success, it reports the KEY NAME, not the value:

```bash
echo "wrote $key_name (${#val} bytes)"
```

The byte count is a useful sanity check (lets you see "PEM key was 1700 bytes, good") without revealing the bytes.

## When the vault is the wrong tool

- **Production secrets stay in production** — a managed secret manager (Azure Key Vault, AWS Secrets Manager / KMS, GCP Secret Manager, HashiCorp Vault). This vault is for the local dev workflow and for re-injecting after a host wipe.
- **Per-user secrets** (an OAuth client secret tied to a specific developer's identity) — those live in the developer's own `.env`, not here.
- **Anything where regeneration is cheaper than backup** — random session keys, ephemeral nonces, etc. Re-generate, do not store.

## Recovery

If `secrets.json` is lost, regenerate from authoritative sources (the upstream provider's dashboard, your CA, your secret manager). The vault is a convenience cache, not a system of record.
