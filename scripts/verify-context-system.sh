#!/usr/bin/env bash
# =============================================================================
# script: verify-context-system.sh
# purpose: End-to-end smoke test of the Rote context system.
#          Runs read-only probes against every surface (HTTP API, vault, DB,
#          delegates, MCP server) and reports PASS / FAIL / WARN per check.
#          A clean pass means future Claude sessions can trust the system.
# inputs:
#   --api <url>      default http://127.0.0.1:5572
#   --no-mcp         skip the MCP-server import check (e.g. no python3 in PATH)
#   --no-delegates   skip live delegate probes (LAN-only checks)
#   --strict         exit non-zero on any WARN as well as any FAIL
# outputs:
#   stdout: per-check PASS/FAIL/WARN lines + summary
#   exit 0 all pass, 1 at least one FAIL, 2 (only with --strict) any WARN,
#          5 bad args
# touches-secrets: no
# when-to-use:    after a fresh clone, after `pip install -r requirements.txt`,
#                 once at the start of each session if you want to be sure,
#                 after restarting the server
# when-NOT-to-use: every commit (this is a system smoke test, not a unit test)
# added: 2026-06-03
# family: verify-context-system
# environment: posix-bash
# =============================================================================
set -uo pipefail

API="${API:-http://127.0.0.1:5572}"
NO_MCP=0
NO_DELEGATES=0
STRICT=0
PASS=0
FAIL=0
WARN=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --api) API="$2"; shift 2 ;;
        --no-mcp) NO_MCP=1; shift ;;
        --no-delegates) NO_DELEGATES=1; shift ;;
        --strict) STRICT=1; shift ;;
        -h|--help) sed -n '3,22p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 5 ;;
    esac
done

pass()  { echo "[PASS] $*"; PASS=$((PASS+1)); }
fail()  { echo "[FAIL] $*" >&2; FAIL=$((FAIL+1)); }
warn()  { echo "[WARN] $*" >&2; WARN=$((WARN+1)); }
note()  { echo "       $*"; }

command -v curl >/dev/null || { echo "[FAIL] curl required to verify" >&2; exit 1; }
command -v jq   >/dev/null || { echo "[FAIL] jq required to verify" >&2; exit 1; }

echo "=== Rote context-system verification ==="
echo "API: $API"
echo

# -----------------------------------------------------------------------------
# 1. API is up + responsive
# -----------------------------------------------------------------------------
if HEALTH=$(curl -fsS -m 5 "$API/healthz" 2>/dev/null); then
    pass "API responding at $API"
    SQLITE_VEC=$(echo "$HEALTH" | jq -r '.sqlite_vec_version // "missing"')
    EMBED_MODEL=$(echo "$HEALTH" | jq -r '.embed_model // "missing"')
    VAULT_EXISTS=$(echo "$HEALTH" | jq -r '.vault_exists')
    note "sqlite-vec=$SQLITE_VEC  embed_model=$EMBED_MODEL  vault_exists=$VAULT_EXISTS"
    if [[ "$SQLITE_VEC" == "missing" || "$SQLITE_VEC" == "null" ]]; then
        fail "sqlite-vec not loaded — semantic search will 500"
    fi
else
    fail "API at $API not reachable. Start it: /path/to/rote/server/start.sh"
    echo
    echo "Cannot continue without API."
    exit 1
fi

# -----------------------------------------------------------------------------
# 2. Scripts endpoint + auto-indexer + embedding works
# -----------------------------------------------------------------------------
if SCRIPTS=$(curl -fsS "$API/scripts" 2>/dev/null); then
    COUNT=$(echo "$SCRIPTS" | jq '.scripts | length')
    if [[ "$COUNT" -gt 0 ]]; then
        pass "scripts indexed ($COUNT)"
        echo "$SCRIPTS" | jq -r '.scripts[].name' | sed 's/^/         /'
    else
        warn "scripts dir indexed empty — drop a .sh in scripts/ before relying on find"
    fi
else
    fail "GET /scripts failed (embedding model may have failed to load; check server.log)"
fi

# Semantic search — triggers full embed model load on first call.
SEARCH=$(curl -fsS -X POST -H "content-type: application/json" \
    -d '{"query":"inject env secrets","limit":1}' \
    "$API/scripts/search" 2>/dev/null)
if echo "$SEARCH" | jq -e '.matches | length > 0' >/dev/null 2>&1; then
    TOP=$(echo "$SEARCH" | jq -r '.matches[0].name')
    pass "semantic search works (top hit: $TOP)"
else
    fail "semantic search failed or empty — embedding model probably not loaded"
fi

# -----------------------------------------------------------------------------
# 3. Anti-patterns
# -----------------------------------------------------------------------------
if AP=$(curl -fsS "$API/anti-patterns" 2>/dev/null); then
    AP_COUNT=$(echo "$AP" | jq '.count')
    if [[ "$AP_COUNT" -ge 10 ]]; then
        pass "anti-patterns catalog populated ($AP_COUNT)"
    elif [[ "$AP_COUNT" -gt 0 ]]; then
        warn "only $AP_COUNT anti-patterns — expected at least 10 from seed"
    else
        fail "anti-patterns catalog empty (seed didn't index)"
    fi
else
    fail "GET /anti-patterns failed"
fi

# -----------------------------------------------------------------------------
# 4. Vault — names-only invariant
# -----------------------------------------------------------------------------
if VAULT=$(curl -fsS "$API/vault/keys" 2>/dev/null); then
    VK_COUNT=$(echo "$VAULT" | jq '.count')
    pass "vault accessible (keys: $VK_COUNT)"
    # Invariant: response never carries a "value" field on any key.
    if echo "$VAULT" | jq -e '.keys[].value' >/dev/null 2>&1; then
        fail "vault response contains 'value' field — secret-handling rule broken"
    fi
else
    fail "GET /vault/keys failed"
fi

# -----------------------------------------------------------------------------
# 5. Delegates registry + best
# -----------------------------------------------------------------------------
if DELEGATES=$(curl -fsS "$API/delegates" 2>/dev/null); then
    D_COUNT=$(echo "$DELEGATES" | jq '.count')
    if [[ "$D_COUNT" -ge 1 ]]; then
        pass "delegate registry populated ($D_COUNT)"
        echo "$DELEGATES" | jq -r '.delegates[] | "         \(.name)\tenabled=\(.enabled)"'
    else
        warn "no delegates registered — best_delegate will always return null"
    fi
else
    fail "GET /delegates failed"
fi

# Live probe of each enabled delegate's URL if --no-delegates not set.
if [[ "$NO_DELEGATES" -eq 0 && -n "${DELEGATES:-}" ]]; then
    ENABLED_URLS=$(echo "$DELEGATES" | jq -r '.delegates[] | select(.enabled == true) | .contact.url // empty')
    while read -r url; do
        [[ -z "$url" ]] && continue
        # Skip URLs with <TBD> placeholders.
        if [[ "$url" == *'<TBD>'* ]]; then
            warn "delegate URL still has <TBD>: $url"
            continue
        fi
        if curl -fsS -o /dev/null -m 5 "$url" 2>/dev/null; then
            pass "delegate URL reachable: $url"
        else
            # Some endpoints (sglang health) need a specific path.
            warn "delegate URL not reachable as-is: $url (probe may need a path suffix like /healthz, /v1/models, /api/tags)"
        fi
    done <<< "$ENABLED_URLS"
fi

# -----------------------------------------------------------------------------
# 6. Audit log writable
# -----------------------------------------------------------------------------
if AUDIT=$(curl -fsS "$API/audit?limit=1" 2>/dev/null); then
    pass "audit log readable"
else
    fail "GET /audit failed"
fi

# -----------------------------------------------------------------------------
# 7. MCP server importable (Python deps installed)
# -----------------------------------------------------------------------------
if [[ "$NO_MCP" -eq 0 ]]; then
    MCP_VENV="$HOME/.cache/rote-mcp/venv"
    [[ -d "$MCP_VENV/bin" ]] || MCP_VENV="/path/to/rote/mcp-server/.venv"
    if [[ -x "$MCP_VENV/bin/python" ]]; then
        if "$MCP_VENV/bin/python" -c "import mcp, httpx" 2>/dev/null; then
            pass "MCP server deps importable (mcp, httpx)"
        else
            fail "MCP venv exists but mcp/httpx not importable — run mcp-server/start.sh once to install"
        fi
    else
        warn "MCP server venv not bootstrapped yet (start mcp-server/start.sh once to create it)"
    fi
fi

# -----------------------------------------------------------------------------
# 8. GUI smoke
# -----------------------------------------------------------------------------
if GUI=$(curl -fsS "$API/" 2>/dev/null); then
    if echo "$GUI" | grep -q 'data-tab=delegates'; then
        pass "GUI served at $API/ (delegates tab present)"
    else
        warn "GUI served but missing expected tab — app.py may be out-of-date"
    fi
else
    fail "GET / (GUI) failed"
fi

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo
echo "=== Summary ==="
echo "PASS=$PASS  FAIL=$FAIL  WARN=$WARN"
if [[ "$FAIL" -gt 0 ]]; then
    echo "Status: NOT READY — fix FAILs before relying on the system."
    exit 1
fi
if [[ "$WARN" -gt 0 && "$STRICT" -eq 1 ]]; then
    echo "Status: READY-WITH-WARNINGS (strict mode → exiting non-zero)"
    exit 2
fi
echo "Status: READY"
exit 0
