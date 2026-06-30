---
name: secret-handling
description: ALWAYS invoke before reading, writing, or moving a secret value (API key, private key PEM, database password, OAuth client secret, OIDC ID-token, JWT signing key, bearer token, etc.). Routes secrets through the local Rote API so the secret BYTES never enter Claude's reasoning context. Refuses to handle a secret directly — points the caller at the deterministic, auditable injection path.
---

# Secret Handling — Out-of-Band Vault Guard Skill

The single rule: **secret values must never enter Claude's reasoning context, transcript, or tool I/O stream.** Claude knows secret NAMES; the local server knows secret VALUES; the two never cross.

## When to invoke

- About to write a `.env` file with a real secret value
- About to read a secret out of a 1Password / Bitwarden / Stripe dashboard and paste it into anything
- About to base64-encode a private key for a Kubernetes Secret
- About to construct an `Authorization: Bearer <token>` header where the token came from somewhere persistent
- About to scp / rsync / cat a file containing secrets
- About to log a request/response that may contain secrets (always sanitize first)
- The user uploaded a credential file and asked you to "use it"

## When NOT to invoke

- Reading a `.env.example` (those have placeholders, not secrets)
- Discussing what KEY NAMES exist
- Generating a brand-new keypair locally that has no value yet (then immediately put it in the vault)

## Hard rules

1. **NEVER** read a secret value into context and then Write it elsewhere. Even if "it's just moving it".
2. **NEVER** echo, cat, print, or otherwise emit a secret to stdout where Claude can see it.
3. **NEVER** ask the user to paste a secret into the chat.
4. **NEVER** base64 / hex / json-encode a secret in conversation. Always do that server-side.
5. The above rules ALSO apply to "fragments" — partial keys, key thumbprints, key fingerprints — anything that uniquely identifies the credential.

## Decision flow

```
about to handle secret X?
├── is X in the local vault?
│   ├── yes  →  use rote vault inject --key X (server reads + writes)
│   └── no   →  STOP. Ask user to add X to the vault out-of-band (see "adding"
│               below); do not try to obtain X via tool calls.
├── about to write X into a .env?  →  rote vault inject
├── about to scp X?                →  ask user to scp; do not transit via tools
└── about to log/show X?           →  redact; show "<KEY_NAME> = (<N> bytes)"
```

## Vault interface (read NAMES only)

```bash
rote vault list
# all keys: name <TAB> bytes

rote vault has KEY1 KEY2
# which exist: KEY1<TAB>true / KEY2<TAB>false
```

## Injection (write VALUES into a .env, server-side only)

```bash
rote vault inject \
    --env-file /abs/path/to/.env \
    --key DATABASE_URL \
    --key STRIPE_SECRET_KEY \
    --key OIDC_CLIENT_SECRET \
    --label "deploy-secrets"
```

What happens server-side:
1. Server reads the vault JSON
2. Renders a labeled block `# >>> deploy-secrets >>> ... # <<< deploy-secrets <<<` into the target `.env`, replacing any prior block with the same label (idempotent)
3. Returns a summary: `wrote: [{name, bytes}], missing: [names]` — names + sizes only, never bytes

If any key is missing, the script exits 3 and the response includes `missing: [...]`. That's the signal to ask the user to add the missing key to the vault (NOT to ask them to paste it in chat).

## Adding a secret to the vault (USER does this, out of band)

Do not write a secret value as part of a tool call. Instead, ask the user to:

1. Open `/path/to/rote/secret-vault/secrets.json` in a real editor (not via Claude)
2. Add the key-value pair (PEM newlines as `\n` escapes; the inject script handles them)
3. Save the file

Then continue with `rote vault inject`.

For one-off bootstrap, you can suggest a one-liner the user runs themselves (not Claude):

```bash
# USER runs this in their own terminal, not via Claude:
KEY_NAME=DATABASE_PASSWORD
read -r -p "value: " -s VAL && echo ""
python3 -c "import json,os; p=os.path.expanduser('/path/to/rote/secret-vault/secrets.json'); d=json.load(open(p)) if os.path.exists(p) else {}; d['$KEY_NAME']=input(); json.dump(d,open(p,'w'),indent=2)" <<< "$VAL"
unset VAL
```

Or simpler: edit the file in vim and save it.

## Detection — am I about to break a rule?

Before any of these tool calls, ask yourself "does this involve a secret value?":

- `Write` with content containing `=ABCDEF...` style strings → STOP, use inject
- `Edit` adding `Authorization: Bearer <token>` → STOP, use inject
- `Bash` with `echo "$SECRET"` or `cat creds.json` → STOP
- `Bash` `scp creds.txt user@host:` → STOP, ask user to scp themselves

If you catch yourself about to do one of these, fall back to the vault flow.

## Recovery if a secret leaks into context

This should NOT happen. If it does (e.g. user pasted a secret in chat):

1. Tell the user the secret is now in the transcript and may be persisted
2. Recommend they ROTATE the secret immediately (revoke + re-issue)
3. Do not echo the secret further in your responses

## Audit trail

Every `/vault/inject` call writes an entry to the audit log with key NAMES + byte counts + target path + timestamp. Never with values. To inspect:

```bash
rote audit 100
```

## Cross-reference

- [[rote]] — discovery + execution of scripts including the vault scripts
- [[chronicle]] — should record any "almost wrote a secret to context" near-misses as an anti-pattern
- See anti-pattern `llm-writes-secrets-into-env` for the failure mode this skill prevents
