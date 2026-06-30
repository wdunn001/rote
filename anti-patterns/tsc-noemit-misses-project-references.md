---
slug: tsc-noemit-misses-project-references
title: tsc --noEmit only checks the root tsconfig — misses errors in referenced sub-projects
category: typescript-build
cost: one wasted deploy cycle (preflight passes, docker build fails 2 minutes in)
---

# Symptom

Local `tsc --noEmit` reports zero errors.  CI / docker / production build runs `tsc -b` (or `tsc -b && vite build`) and fails with errors in files the preflight should have caught.  Discrepancy makes the preflight look broken.

# Root cause

`tsc --noEmit` without `-b` only checks files included in the root `tsconfig.json`.  In a project-reference setup (`tsconfig.json` with `references: [{ path: "./apps/foo" }, { path: "./packages/bar" }]`), errors in the referenced sub-projects are **not surfaced** by plain `--noEmit`.

`tsc -b` (build mode) walks the project graph the same way `tsc --build` would — it covers every referenced project AND uses the strict-mode flags each one declares in its own tsconfig.  That matches what the docker build actually runs.

# Remedy

Use `tsc -b --noEmit` for any preflight / pre-commit / local-check invocation.  The `--noEmit` flag prevents the project from writing out `.tsbuildinfo` / dist artifacts; `-b` keeps the project-graph traversal.

```sh
# WRONG — silent on referenced-project errors
./node_modules/.bin/tsc --noEmit

# RIGHT — matches what the build does
./node_modules/.bin/tsc -b --noEmit
```

For a deploy script's local preflight:

```js
const res = spawnSync(
  path.join(webDir, "node_modules", ".bin", "tsc"),
  ["-b", "--noEmit"],
  { cwd: webDir, stdio: ["ignore", "inherit", "inherit"] },
);
```

# Trade-off

`tsc -b --noEmit` is slower than plain `--noEmit` — typically 2-3x (90 s vs 30 s on the example-app web SPA).  For deploy preflight that's a strict win (catches more errors).  For pre-commit hooks the overhead may matter; offer a `tsc -b --noEmit --incremental` mode that uses the `.tsbuildinfo` cache.

# How it slipped past

Most TypeScript guides default to `tsc --noEmit` for "fast typecheck" without mentioning project references.  Anyone copying the pattern into a monorepo with references gets the false-green silently.

# Related

- [[deploy-cost-ramp-preflight-first]] — preflight strategy.

# Real-world hit

Shipped on `example-app` 2026-06-04 commit `e3997eef`.  Initial preflight in commit `caa038e8` used plain `tsc --noEmit`, passed, then docker's `tsc -b` failed on a TS2367 in `GcsFirstLaunchEnrollmentPage.tsx` that the plain mode hadn't checked.
