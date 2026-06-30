---
slug: deploy-cost-ramp-preflight-first
name: Deploy cost-ramp — fast-fail at the cheapest stage
category: architectural
intent: Order deploy-pipeline stages by wall-clock so failures surface at the earliest stage that can catch them, never burn an expensive stage on a check a cheaper stage could have run
references: |
  GitLab CI documentation on stage ordering; "shift left" testing literature.
  Real-world: example-app/scripts/deploy.cjs preflight.
---

# When to use

You have a multi-stage deploy pipeline where each stage has a meaningfully different wall-clock cost.  Failures at any stage abort the whole deploy.  You want operators to know within seconds, not minutes, when something is wrong.

Typical for: docker-image-building monorepo deploys, multi-app rolling deploys, infrastructure-as-code apply chains, anything with a "build → publish → release → migrate" structure.

# When NOT to use

Single-stage deploys (e.g. `git push` to Vercel that does everything in one server-side step).  Tiny apps where every stage is under 30 s anyway.  Highly-coupled stages where a "cheap" check actually requires the expensive previous stage to have run (rare).

# Structure

Cost-rank each stage by wall-clock + non-recoverable side effects.  Reorder so the most-likely-to-fail check happens at the cheapest stage that has enough information to run it.

For a docker-building monorepo:

| Stage | Typical cost | What it should catch |
|---|---|---|
| 1. Local preflight | 30-120 s | Type errors, linting, missing deps, env-var validation, secret presence checks |
| 2. Docker build | 1-5 min | Native dep compilation, image-time runtime errors |
| 3. scp / upload | 10-60 s | Network, auth, disk-space |
| 4. compose down + up | 30-90 s | Container startup, healthcheck pass, port bind |
| 5. Migration / smoke | 10-60 s | DB migration, post-deploy probe |

Each stage's expected failures should bail BEFORE the next stage's wall-clock starts.  Local preflight should typecheck what the docker stage would have typechecked.  Docker build should exhaustively validate before scp uploads a broken image.

```js
// scripts/deploy.cjs preflight before docker
if (composeCmdBuildsDockerImages(composeCmd)) {
  if (!truthyEnv(env.DEPLOY_SKIP_WEB_PREFLIGHT_TYPECHECK)) {
    const webTsc = path.join(root, "apps", "web", "node_modules", ".bin", "tsc");
    if (fs.existsSync(webTsc)) {
      console.log("Preflight: typecheck apps/web (tsc -b --noEmit)…");
      const res = spawnSync(webTsc, ["-b", "--noEmit"], { cwd: webDir, stdio: ["ignore", "inherit", "inherit"] });
      if (res.status !== 0) process.exit(res.status ?? 1);
    }
  }
  hasLocalNativeSo = ensureLinuxNativeForDockerDeploy(root, env);
}
```

# Rules

1. **Every preflight check has a bypass env var.**  Operators legitimately need to deploy server-only changes on top of known-broken web sometimes.  Don't hard-block.
2. **Preflight uses the SAME tool the build stage uses.**  If docker runs `tsc -b`, preflight runs `tsc -b --noEmit`.  Don't preflight with a weaker check.
3. **No silent skips.**  If preflight can't run (missing node_modules, missing CLI), warn loudly — don't silently let the slower stage catch the error.
4. **Log timing on success.**  "Preflight OK in 87 s" tells operators what they saved.

# Related

- [[tsc-noemit-misses-project-references]] — common subtle bug in TS preflight.

# Real-world implementation

`example-app/scripts/deploy.cjs` commit `caa038e8` (initial) → `e3997eef` (strengthened to `tsc -b --noEmit`).  Turns a typical 3-minute docker-build failure into a 90-second local failure.
