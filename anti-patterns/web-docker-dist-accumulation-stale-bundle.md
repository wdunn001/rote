---
slug: web-docker-dist-accumulation-stale-bundle
title: Multi-stage SPA Docker build never cleans dist — serves stale entry + orphaned fresh chunks
hit_count: 1
token_cost: high — every web change silently swallowed across many deploys; long diagnostic arc (HTTP probing + container inspection) to find it; user sees "none of it" after "done"
---

# Symptom

You deploy a vite/webpack SPA via a multi-stage Docker build. The deploy succeeds, the new content-hashed asset files ARE on the server (HTTP 200), the container rebuilt, the container recreated — yet the live site loads OLD code. The served `index.html` references an old entry bundle (`index-OLDHASH.js`); the new code's chunk (e.g. `MyPage-NEWHASH.js`) exists in the container but is **orphaned** (no entry references it). The user "sees none of" a feature that was built, committed, and deployed.

# Root cause

The Dockerfile runs `npm run build` with **no clean of the output dir**, and the final (nginx) stage `COPY`s dist over a web root it never clears. Content-hashed bundlers name each chunk by content, so across builds `dist` ACCUMULATES: old `index.html` + old entry survive while new chunks are added. The served `index.html` is the old one, pointing at the old entry, which never references the new chunks. `--no-cache` does NOT fix this — the accumulation is in the output dir / web root, not the layer cache. (Operators often blame caching; verify the cache config first — it's usually already off.)

# Remedy (deterministic)

Clean both the build output dir AND the nginx web root every build:

```dockerfile
# build stage
RUN rm -rf dist && npm run build
# nginx stage
RUN rm -rf /usr/share/nginx/html/*
COPY --from=build /src/apps/web/dist /usr/share/nginx/html
```

Apply to EVERY SPA image (marketing/free/leet/etc.) — they all have the bug if they share the pattern.

# Detection

Don't trust "build finished" + "assets return 200." Compare the SERVED entry hash to the build log's emitted hashes:

```bash
# what the build produced:
grep -oE "dist/assets/index-[A-Za-z0-9_-]+\.js" deploy.log | sort -u
# what's actually served (note: vite hashes can contain '-'):
curl -fsS https://APP/ | grep -oE '/assets/index-[A-Za-z0-9_-]+\.js'
```

If the served entry hash is NOT in the build log, the web root is serving an accumulated/stale bundle. Also: fetch the served entry JS and grep it for the new chunk's filename — if absent, the entry is stale even though the chunk exists on disk. Best fix long-term: a deploy post-check that asserts the served `index-*.js` is one this build emitted.
