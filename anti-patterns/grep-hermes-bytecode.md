---
slug: grep-hermes-bytecode
title: Grep on Hermes bytecode bundle returns 0 matches even when the string is there
hit_count: 1
token_cost: medium — wasted debugging cycle, can compound with [[apk-rebuild-stale-bundle]]
---

# Symptom

You want to confirm a JS string made it into the production React Native bundle. You run `grep -c "MY_STRING" android/app/build/generated/assets/createBundleReleaseJsAndAssets/index.android.bundle` and get **0 matches**. You conclude the bundle is stale, but it isn't.

# Root cause

Hermes compiles JS to bytecode; string literals are interned in a separate constant pool and stored in a binary format that grep can't see as plain text.

# Remedy

Grep the **sourcemap**, not the bundle:

```bash
grep -c "MY_STRING" android/app/build/generated/sourcemaps/react/release/index.android.bundle.map
```

The sourcemap is plain JSON containing every original-source string, even after Hermes compilation. Non-zero means the string is in the bundle.

# Detection

Anytime you want to "is X in the bundle" and you reach for `grep` on `index.android.bundle`: switch to the sourcemap.

# See also

- [[apk-rebuild-stale-bundle]]
