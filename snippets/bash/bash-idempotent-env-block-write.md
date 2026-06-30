---
slug: bash-idempotent-env-block-write
name: Bash idempotent labeled-block .env writer
language: bash
applies_patterns: idempotency-token
applies_technologies: 
references: 
---

# When to use
Append KEY=VALUE lines inside a labeled block in a .env file so the writer
is idempotent — re-running replaces the prior block atomically rather than
duplicating.

# When NOT to use
Single-key replacement (just sed).

Values contain secrets — use the vault inject API instead.

# Placeholders
- ENV_FILE: absolute path to the .env file (example: /srv/app/.env)
- BLOCK_LABEL: unique label so re-runs replace the same block (example: deploy-secrets)
- KEY_VALUES: newline-separated KEY=VALUE pairs (example: FOO=bar\nBAZ=qux)

# Snippet
```bash
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
}
```

# Example expansion
See scripts/inject-env-secrets.sh + the /vault/inject server-side implementation.
