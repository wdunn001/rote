---
slug: per-folder-grounding-workflow
name: Per-Folder Grounding Workflow
category: architectural
intent: Before integrating a feature into a large unfamiliar codebase, fan out one read-only agent per folder to report what the code ACTUALLY does (and where docs lie), then synthesize the design from ground truth
references: mz-halow-bridge HaLow transport integration (2026-06); Workflow tool
---

# When to use
You must add a feature (a transport, a strategy, an adapter) to a system too large to hold in one context, and you need the real extension points, not the ones the README claims.

You have a work-list of folders/READMEs you can enumerate cheaply up front (scout inline first).

Correctness depends on what the code does today (registration mechanism, naming discipline, the closest existing analog), and getting it wrong means a wasted scaffold.

Example: integrating Wi-Fi HaLow into mz-pid-tuner. One agent per `src/platforms/*`, `src/app`, `test`, etc. reported the actual `IGcsLink` factory/registry mechanism and flagged README-vs-code drift; the synthesis stage produced a scaffold that matched the DeviceA analog exactly.

# When NOT to use
The codebase is small enough to read directly (just read it).

The folders are uniform boilerplate (one overview agent beats N redundant agents; fold them).

You only need a single fact you already know the location of (grep, do not orchestrate).

# Structure
1. Scout inline: enumerate the folders/READMEs (the work-list). Fold uniform families (e.g. 22 identical detector dirs) into one overview agent; log that cap, do not silently drop.
2. Analyze (barrier): one read-only agent per folder, each forced to a structured schema { actual_purpose, key_files, key_interfaces, patterns_used, how_to_extend, readme_vs_code_drift, relevance }. Instruct: read the code, never infer from names; report doc-vs-code mismatches explicitly.
3. Design (barrier on the full analysis set): synthesis agents that also read the real seam files directly, producing an exact file manifest grounded in the closest existing analog.
4. Scaffold in-loop: the main loop writes files from the manifest so the result is coherent (avoid racing file-writer agents on shared files).

# Notes
Pairs with the capability-descriptor pattern (design the seam from the capability, not the instance) and the cross-repo-contract-drift-guard (lock the synthesized contract against its mirrors). The analysis stage is where "verify docs against code" is enforced at scale.
