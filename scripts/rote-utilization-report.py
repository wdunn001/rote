#!/usr/bin/env python3
# =============================================================================
# script: rote-utilization-report.py
# purpose: Diagnose how much each Rote catalog surface is ACTUALLY
#          used vs merely populated. For every surface (scripts, design-patterns,
#          technologies, snippets, stacks, commands, anti-patterns, delegates,
#          delegations, vault) it reports: total entries, total recorded uses,
#          and how many entries have ZERO uses ("documented but never load-
#          bearing"). Also flags CLI/skill drift: catalog surfaces the installed
#          `rote` CLI has NO subcommand for (so skills that tell Claude to
#          call them silently fail). Answers "is the AI skill ecosystem getting
#          exercised, and if not, where's the gap?"
# inputs:
#   --api <url>        base API (default http://127.0.0.1:5572)
#   --cli <path>       rote path (default /path/to/rote/cli/rote)
#   --json             emit machine-readable JSON instead of the text report
# outputs: a utilization table on stdout; exit 0 ok, 1 API unreachable
# touches-secrets: no (vault: counts NAMES only, never values)
# when-to-use:    auditing whether the library's catalogs are paying off;
#                 spotting CLI/skill drift; before deciding to prune or promote
# when-NOT-to-use: you just want one surface's contents — use rote list etc.
# added: 2026-06-17
# family: rote-utilization-report
# environment: cross-python
# =============================================================================
import argparse
import json
import subprocess
import sys
import urllib.request

# candidate field names a catalog row might use to record "times applied"
USE_KEYS = ("use_count", "uses", "used_count", "times_used", "hit_count", "hits", "apply_count")
# the wrapper key -> the list inside each endpoint's JSON envelope
ENDPOINTS = {
    "scripts": "scripts",
    "design-patterns": "design_patterns",
    "technologies": "technologies",
    "snippets": "snippets",
    "stacks": "stacks",
    "commands": "commands",
    "anti-patterns": "anti_patterns",
    "delegates": "delegates",
    "vault": "secrets",
}
# which surfaces the design-patterns / local-delegate / secret-handling skills
# instruct Claude to drive, and the rote subcommand they tell it to use.
SKILL_SUBCOMMANDS = {
    "design-patterns": "dp",
    "technologies": "tech",
    "snippets": "snippet",
    "stacks": "stack",
    "commands": "cmd",
    "delegates": "delegate",
    "anti-patterns": "ap",
    "vault": "vault",
}


def get(api, path):
    with urllib.request.urlopen(f"{api}/{path}", timeout=10) as r:
        return json.load(r)


def as_list(payload, wrapper):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if wrapper in payload and isinstance(payload[wrapper], list):
            return payload[wrapper]
        for v in payload.values():  # fall back to first list value
            if isinstance(v, list):
                return v
    return []


def use_of(row):
    for k in USE_KEYS:
        if isinstance(row, dict) and isinstance(row.get(k), int):
            return row[k]
    return None


def cli_subcommands(cli):
    """Probe each subcommand for REAL existence by running `<cli> <sub> list`.
    Do NOT parse --help: the help text is incomplete (omits dp/tech/snippet/
    stack/cmd) even though those subcommands work — parsing help gives a false
    'missing' verdict. Implemented == exit 0 or output that isn't an error."""
    found = set()
    for token in ("dp", "tech", "snippet", "stack", "cmd", "delegate", "ap", "vault"):
        try:
            r = subprocess.run([cli, token, "list"], capture_output=True, text=True, timeout=15)
        except Exception:
            continue
        blob = (r.stdout + r.stderr).lower()
        missing = ("unknown" in blob and "subcommand" in blob) or "no such" in blob
        if r.returncode == 0 and not missing:
            found.add(token)
    return found


def search_health(cli):
    """Semantic search is the front door to every catalog. If query embedding is
    broken, every `find` collapses to ~uniform max distance and returns noise.
    Probe with a query that has an obvious answer and inspect the top distance."""
    probes = [("dp", "circuit breaker for a flaky downstream service", "circuit-breaker"),
              ("snippet", "write an env file idempotently", "env")]
    results = []
    for sub, query, expect in probes:
        try:
            r = subprocess.run([cli, sub, "find", query], capture_output=True, text=True, timeout=20)
            lines = [l for l in r.stdout.splitlines() if l.strip()]
            dists = []
            for l in lines:
                for f in l.split("\t"):
                    try:
                        dists.append(float(f))
                        break
                    except ValueError:
                        continue
            top = min(dists) if dists else None
            hit = any(expect in l.lower() for l in lines[:3])
            results.append({"sub": sub, "query": query, "top_distance": top,
                            "expected_in_top3": hit})
        except Exception as e:
            results.append({"sub": sub, "query": query, "error": str(e)})
    # broken if every top distance is >= 0.99 (degenerate / uniform)
    tops = [r.get("top_distance") for r in results if r.get("top_distance") is not None]
    broken = bool(tops) and all(t >= 0.99 for t in tops)
    return {"probes": results, "search_broken": broken}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:5572")
    ap.add_argument("--cli", default="/path/to/rote/cli/rote")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        get(args.api, "healthz")
    except Exception as e:
        print(f"API unreachable at {args.api}: {e}", file=sys.stderr)
        return 1

    report = {}
    for ep, wrapper in ENDPOINTS.items():
        try:
            rows = as_list(get(args.api, ep), wrapper)
        except Exception as e:
            report[ep] = {"error": str(e)}
            continue
        uses = [use_of(r) for r in rows]
        tracked = [u for u in uses if u is not None]
        report[ep] = {
            "entries": len(rows),
            "use_tracked": len(tracked) > 0,
            "total_uses": sum(tracked) if tracked else None,
            "zero_use": (sum(1 for u in tracked if u == 0) if tracked else None),
        }

    # delegations = the actual utilization log for delegates
    try:
        events = as_list(get(args.api, "delegations"), "events")
        by_outcome, by_delegate, savings = {}, {}, 0
        latest = 0
        for e in events:
            by_outcome[e.get("outcome", "?")] = by_outcome.get(e.get("outcome", "?"), 0) + 1
            by_delegate[e.get("delegate", "?")] = by_delegate.get(e.get("delegate", "?"), 0) + 1
            savings += e.get("token_savings") or 0
            latest = max(latest, e.get("ts_unix_ms") or 0)
        report["delegations"] = {
            "events": len(events), "by_outcome": by_outcome,
            "by_delegate": by_delegate, "total_token_savings": savings,
            "latest_ts_ms": latest,
        }
    except Exception as e:
        report["delegations"] = {"error": str(e)}

    impl = cli_subcommands(args.cli)
    drift = {ep: sub for ep, sub in SKILL_SUBCOMMANDS.items()
             if sub in ("dp", "tech", "snippet", "stack", "cmd", "delegate", "ap", "vault")
             and sub not in impl}
    report["_cli_drift"] = {
        "implemented_subcommands": sorted(impl),
        "skill_invokes_but_cli_missing": drift,
    }
    report["_search"] = search_health(args.cli)

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    print("=" * 64)
    print(" SCRIPT LIBRARY — CATALOG UTILIZATION REPORT")
    print("=" * 64)
    hdr = f"{'surface':<18}{'entries':>9}{'uses':>8}{'zero-use':>10}  notes"
    print(hdr)
    print("-" * len(hdr))
    for ep in ENDPOINTS:
        r = report.get(ep, {})
        if "error" in r:
            print(f"{ep:<18}{'ERR':>9}  {r['error'][:30]}")
            continue
        uses = r["total_uses"]
        zero = r["zero_use"]
        note = ""
        if not r["use_tracked"]:
            note = "no use-tracking field"
        elif uses == 0:
            note = "!! populated but NEVER used"
        elif zero and r["entries"]:
            note = f"{zero}/{r['entries']} entries never used"
        print(f"{ep:<18}{r['entries']:>9}"
              f"{(uses if uses is not None else '-'):>8}"
              f"{(zero if zero is not None else '-'):>10}  {note}")

    d = report["delegations"]
    print("-" * len(hdr))
    if "error" not in d:
        print(f"delegations (the delegate utilization log): {d['events']} events, "
              f"outcomes={d['by_outcome']}, ~{d['total_token_savings']:,} tokens saved")
        print(f"   per-delegate: {d['by_delegate']}")

    cd = report["_cli_drift"]
    print("-" * len(hdr))
    print("CLI SUBCOMMANDS (probed, not parsed from --help):")
    if cd["skill_invokes_but_cli_missing"]:
        print("  MISSING (skill invokes, CLI lacks):", cd["skill_invokes_but_cli_missing"])
    else:
        print("  all skill-invoked subcommands exist:", ", ".join(cd["implemented_subcommands"]))

    s = report["_search"]
    print("-" * len(hdr))
    print("SEMANTIC SEARCH HEALTH (the real front door):")
    if s["search_broken"]:
        print("  !! BROKEN — every `find` returns ~uniform max distance (degenerate")
        print("     embeddings). The catalogs are invisible through search. Likely the")
        print("     embedding endpoint is down. THIS is the utilization killer.")
    else:
        print("  search returns discriminating distances (ok)")
    for p in s["probes"]:
        if "error" in p:
            print(f"    {p['sub']} find: ERROR {p['error']}")
        else:
            print(f"    {p['sub']} find '{p['query'][:32]}...': top_dist={p['top_distance']} "
                  f"expected_in_top3={p['expected_in_top3']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
