#!/usr/bin/env bash
# =============================================================================
# Rote codec-web demo
#
# Shows Rote acting as the local switchboard in front of a cloud coordinator,
# the division of labor argued for in The Mild Take's codec-web pieces:
#
#   1. DOOMED-PROMPT PRE-CHECK runs locally and rejects prompts that would
#      waste a remote round-trip (empty, oversized, secret-bearing).
#   2. CLIENT-SIDE VAULT INJECT keeps a needed secret on the edge: the byte
#      value goes into a local tool call, never into the prompt sent remote.
#   3. DELEGATE DISPATCH sends the surviving bulk work to compute you own and
#      logs the token savings, so the cloud only coordinates a few calls.
#
# Runs with no arguments. If a Rote server and a local delegate are reachable
# it uses them; otherwise it SIMULATES the dispatch so the demo always runs.
# It never sends a secret anywhere.
# =============================================================================
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
SCRIPTS="$REPO/scripts"
API="${API:-http://127.0.0.1:5572}"
DELEGATE="${DELEGATE:-local-llm}"

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
rule() { printf '%s\n' "------------------------------------------------------------"; }

api_up() { curl -fsS "$API/healthz" >/dev/null 2>&1; }
delegate_ready() {
    api_up || return 1
    local url
    url=$(curl -fsS "$API/delegates/$DELEGATE" 2>/dev/null | jq -r '.contact.url // empty')
    [[ -n "$url" ]] || return 1
    # is the delegate itself answering?
    curl -fsS "$url" >/dev/null 2>&1 || curl -fsS "${url%/v1}/api/tags" >/dev/null 2>&1
}

# --- the candidate batch: a realistic mix an agent-to-agent pipeline produces -
# Three are structurally doomed. One is good but needs a secret. One is good.
PROMPTS=(
  "Summarize the following changelog into three bullet points: Added retry with backoff to the payment client; fixed a stale-balance race in the ledger; bumped the SDK to 4.2."
  "   "
  "Classify this support ticket as billing/bug/feature. Auth token to read the ticket: sk-ABCD1234abcd5678EFGH9012ijklMNOP3456"
  "GOOD_BUT_NEEDS_SECRET"
  "$(printf 'x%.0s' {1..40000})"
)
LABELS=(
  "valid summarization task"
  "empty/whitespace prompt"
  "prompt carrying a raw API key"
  "task needing a secret (handled via vault)"
  "oversized 40k-char prompt"
)

bold "Rote codec-web demo"
rule
if api_up; then echo "Rote API: up at $API"; else echo "Rote API: not running (vault + logging will be SIMULATED)"; fi
if delegate_ready; then echo "Delegate '$DELEGATE': reachable (real dispatch)"; else echo "Delegate '$DELEGATE': not reachable (dispatch will be SIMULATED)"; fi
rule

caught=0; sent=0; secrets_kept=0

bold "Step 1 + 2: local pre-check + client-side vault inject"
for i in "${!PROMPTS[@]}"; do
    label="${LABELS[$i]}"
    p="${PROMPTS[$i]}"

    # The "needs a secret" case: build the LOCAL tool call by injecting from the
    # vault, and construct a REMOTE-safe prompt that references the secret by
    # NAME only. The secret bytes stay on this machine.
    if [[ "$p" == "GOOD_BUT_NEEDS_SECRET" ]]; then
        printf '  [%d] %-42s ' "$i" "$label"
        if api_up; then
            envdir="$(mktemp -d)"; envf="$envdir/inject.env"   # server requires a *.env target
            # vault inject prints {wrote:[{name,bytes}]}, never the value.
            inj=$(bash "$SCRIPTS/inject-env-secrets.sh" --env-file "$envf" --key SERVICE_BEARER_TOKEN --label codec-web-demo --api "$API" 2>/dev/null || true)
            bytes=$(printf '%s' "$inj" | jq -r '.wrote[]? | "\(.name)=\(.bytes)B"' 2>/dev/null | paste -sd, -)
            rm -rf "$envdir"
            if [[ -n "$bytes" ]]; then
                echo "VAULT  injected locally ($bytes); remote prompt carries the NAME only"
                secrets_kept=$((secrets_kept+1))
            else
                echo "VAULT  key absent (add SERVICE_BEARER_TOKEN to secret-vault/secrets.json to see this); skipping"
            fi
        else
            echo "VAULT  (simulated) secret would be injected locally; remote prompt carries the NAME only"
            secrets_kept=$((secrets_kept+1))
        fi
        # This task survives to dispatch with a placeholder, not a secret.
        SURVIVOR="Using the service identified by \$SERVICE_BEARER_TOKEN, classify the attached record. (token injected locally, not included here)"
        sent=$((sent+1))
        continue
    fi

    printf '  [%d] %-42s ' "$i" "$label"
    res=$(bash "$SCRIPTS/doomed-prompt-precheck.sh" --prompt "$p" 2>/dev/null); rc=$?
    reason=$(printf '%s' "$res" | cut -f2-)
    if [[ $rc -eq 10 ]]; then
        echo "DOOMED caught locally -> $reason"
        caught=$((caught+1))
    else
        echo "PASS   safe to send"
        sent=$((sent+1))
        LAST_GOOD="$p"
    fi
done
rule

bold "Step 3: dispatch the surviving bulk work to compute you own"
GOOD_PROMPT="${LAST_GOOD:-Summarize: the quick brown fox.}"
if delegate_ready; then
    echo "Dispatching one passing prompt to delegate '$DELEGATE' (real call, logs token savings)..."
    bash "$SCRIPTS/dispatch-to-ollama.sh" \
        --delegate "$DELEGATE" --capability bulk-summarization \
        --prompt "$GOOD_PROMPT" --task "codec-web demo summarization" \
        --estimated-saved 180 --api "$API" || echo "(delegate call failed; see stderr)"
else
    echo "(simulated) Would dispatch the passing prompt to '$DELEGATE' and POST the outcome"
    echo "            to $API/delegations with an estimated token saving. With a real"
    echo "            delegate configured, this is one cheap call to owned hardware."
fi
rule

bold "Result"
echo "  doomed prompts caught locally : $caught   (each one a remote round-trip NOT paid)"
echo "  secrets kept on the edge      : $secrets_kept   (secret bytes never sent to a remote model)"
echo "  prompts that reached dispatch : $sent"
echo
echo "The cloud's job shrank from metering every prompt to coordinating the few"
echo "that survived a deterministic, local screen. That is the codec-web division"
echo "of labor: a lightweight switchboard, not a tollbooth on every exchange."
