#!/usr/bin/env python3
# =============================================================================
# script: surface-library-context.py
# purpose: Claude Code UserPromptSubmit hook. On each prompt it does ONE unified
#          semantic search (/search-all) across every Rote catalog and,
#          if the best hits are relevant enough, injects a compact reminder of
#          them as context — so the library SURFACES ITSELF instead of relying on
#          Claude to remember to search. This is the fix for chronic catalog
#          under-utilization. Fail-silent: any error/timeout -> no output, exit 0
#          (never block or corrupt the user's prompt).
# inputs:  hook JSON on stdin ({"prompt": "...", ...})
# outputs: stdout = additional context (or nothing); always exit 0
# env:
#   SL_API           API base (default http://127.0.0.1:5572)
#   SL_MAX_DISTANCE  only surface hits at/below this distance (default 0.82)
#   SL_MAX_HITS      max entries to inject (default 3)
#   SL_MIN_PROMPT    skip prompts shorter than this many chars (default 16)
# touches-secrets: no
# added: 2026-06-17
# family: surface-library-context
# environment: cross-python
# =============================================================================
import json
import os
import sys
import urllib.request

API = os.environ.get("SL_API", "http://127.0.0.1:5572").rstrip("/")
MAX_DISTANCE = float(os.environ.get("SL_MAX_DISTANCE", "0.82"))
MAX_HITS = int(os.environ.get("SL_MAX_HITS", "3"))
MIN_PROMPT = int(os.environ.get("SL_MIN_PROMPT", "16"))
SURFACE_HINT = {
    "prompt": "prompt", "script": "script", "snippet": "snippet",
    "pattern": "dp", "command": "cmd", "anti-pattern": "ap",
}


def main() -> int:
    try:
        # Read raw bytes + decode utf-8-sig so a BOM (e.g. from a Windows pipe)
        # doesn't break json.loads.
        raw = sys.stdin.buffer.read().decode("utf-8-sig", errors="replace")
        prompt = (json.loads(raw).get("prompt") if raw.strip() else "") or ""
    except Exception:
        return 0
    prompt = prompt.strip()
    # Skip trivial prompts and slash-commands (they're not library-shaped work).
    if len(prompt) < MIN_PROMPT or prompt.startswith("/"):
        return 0
    try:
        body = json.dumps({"query": prompt, "limit": MAX_HITS, "per_surface": 2}).encode()
        req = urllib.request.Request(
            f"{API}/search-all", data=body, headers={"content-type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=3.0) as r:
            matches = json.load(r).get("matches", [])
    except Exception:
        return 0  # API down / slow / unreachable — stay silent

    hits = [m for m in matches if m.get("distance", 9) <= MAX_DISTANCE][:MAX_HITS]
    if not hits:
        return 0

    lines = ["<system-reminder>",
             "Rote entries may be relevant to this request "
             "(consult BEFORE reinventing; ignore if off-target):"]
    for m in hits:
        sub = SURFACE_HINT.get(m["surface"], m["surface"])
        label = (m.get("label") or "").strip()
        lines.append(f"  - [{m['surface']}] {m['slug']}"
                     + (f" — {label}" if label else "")
                     + f"  (load: rote {sub} show {m['slug']})")
    lines.append("</system-reminder>")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
