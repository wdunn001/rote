---
slug: parallel-fanout
name: Parallel Fan-Out (independent work concurrently)
category: efficiency
tags: parallelism, fan-out, agents, throughput
---

# Prompt

For ${TASK}, first decompose the work into independent units that don't depend on each other's output, then run them concurrently rather than sequentially.

1. List the units and mark any dependencies between them (A must finish before B).
2. Group the independent ones into a parallel batch; keep the dependent ones in order after their prerequisite.
3. Launch the independent batch together (parallel tool calls / subagents), one focused unit each.
4. Collect results, then do the dependent steps.
5. Synthesize into one coherent result — don't just concatenate the pieces.

If the units would conflict on shared state (same files, same resource), isolate them or serialize just those. Note anything you had to serialize and why.

# When to use

A task that breaks into independent sub-tasks (multi-file edits, multi-source research, broad search) where sequential execution wastes wall-clock.
