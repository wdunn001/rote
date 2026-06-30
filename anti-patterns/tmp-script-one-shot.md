---
slug: tmp-script-one-shot
title: Writing a script to /tmp/, running it once, throwing it out
hit_count: 5
token_cost: high — each rewrite costs the same tokens the first one did, and the next session can't find it because it's not in the library
---

# Symptom

Claude writes a script to `/tmp/foo.sh`, runs it once, never thinks about it again. Same operation needed next session → write a new `/tmp/bar.sh` that does 80% the same thing. Two sessions later: a third `/tmp/baz.sh`. None of the three are discoverable by anyone.

Same pattern with inline `bash -c '<long string>'` and unstructured `ssh user@host "<long string>"` invocations — the work product gets lost in tool-call history.

# Root cause

`/tmp` is the path of least resistance when "this is a quick one-off." The token cost of writing to `/tmp/` is identical to writing to `/path/to/rote/scripts/` — the only difference is the path string. The frontmatter is the only extra cost, and `rote new <name> "<purpose>"` scaffolds that for free.

# Remedy

**Hard rule:** never write a script to `/tmp/`. The destination is always `/path/to/rote/scripts/<name>.sh`. Scaffold via:

```bash
rote new my-thing.sh "one-line purpose"
```

Then fill in the body. Even if the script only ever runs once, the next session can semantic-search for it (`rote find "<symptom>"`) and decide whether to extend, fork, or re-use.

For ad-hoc shell ops that genuinely DON'T need to be persisted (one-line `curl`, one-line `ls`), just run them. The library is for ANY operation of more than ~5 lines OR ANY operation that has parameters that vary.

# Detection

Any time you're about to type `cat > /tmp/...` or `bash -c '<10+ lines>'` or `ssh host "<complex shell>"`: stop. Scaffold instead.

Greppable smell: the script body in your tool call contains `mktemp`, `/tmp/`, or a heredoc longer than 20 lines.

# See also

- [[rote]] skill — fastest scaffolding path
- [[code-rewrite-line-by-line]] anti-pattern — its sibling
