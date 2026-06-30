---
slug: code-rewrite-line-by-line
title: Copying code or doing find/replace by Read-then-Write-line-by-line instead of using generic tools
hit_count: 4
token_cost: high — each line costs Edit/Write tokens, multi-file ops compound, and the result is fragile to the line-numbers being slightly off
---

# Symptom

Claude needs to copy a function from `src/foo.ts` into `src/bar.ts`. Path of least resistance: Read source, Read destination, then a stream of Edit tool calls that rebuild the function in the destination line by line. Equivalent shape when doing a codebase-wide rename: Read N files, run sed-like substitutions through Edit calls one at a time.

The result: 100s of edit tokens to do what `sed -i` or a 5-line bash script handles in one call.

# Root cause

Read + Write + Edit are the natural Claude tools, so they get reached for first. They're also the wrong tool for repetitive mechanical edits: the LLM cost is per-call and per-token, while a generic shell tool's cost is constant in the number of substitutions.

# Remedy

**For codebase-wide find-and-replace:**

```bash
/path/to/rote/scripts/find-replace-tree.sh \
    --root . \
    --include '\.tsx?$' \
    --from "old_string" --to "new_string" \
    --dry-run
# review the per-file change summary, then re-run without --dry-run
```

Handles backup, gitignore awareness, glob filtering, binary-file skipping, and per-file diff summary in one call.

**For copying a code block between files:**

```bash
/path/to/rote/scripts/copy-code-block.sh \
    --src src/foo.ts \
    --src-from '^export function myThing' \
    --src-to '^}$' \
    --dst src/bar.ts \
    --dst-anchor '^// === inserts go here ===' \
    --transform 'sed s/foo/bar/g'
```

Anchored extract, optional transform pipe, optional anchored insert vs labeled-block replace. One call, atomic.

**For "move" instead of "copy": use `--dst-replace-block` to drop the block at the destination, then a follow-up `find-replace-tree --from "<block-marker>" --to ""` to clean the source.**

# Detection

Any time you've made 3+ Edit calls to the same file in a row with similar shapes (same struct change at different lines), OR you're Reading two files to mirror content between them: stop. Reach for `find-replace-tree.sh` or `copy-code-block.sh` instead.

Greppable smell in your tool history: 5+ `Edit` calls within one turn, all on the same file, doing variations of the same substitution.

# See also

- [[rote]] skill — the generic shell tools live there
- [[tmp-script-one-shot]] anti-pattern — its sibling failure mode
