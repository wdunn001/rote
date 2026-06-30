---
slug: npm-ci-vs-install
name: npm ci vs npm install
family: package-mgmt
platform: cross-platform
equivalents: yarn install --frozen-lockfile; pnpm install --frozen-lockfile
references: https://docs.npmjs.com/cli/v10/commands/npm-ci
---

# Command
```sh
npm ci   # CI / reproducible
npm install   # dev / mutating
```

# When to use
CI, Docker builds, reproducible installs — `npm ci`. Local dev where you ARE changing package.json — `npm install`.

# When NOT to use
Don't `npm install` in CI: it can mutate package-lock.json silently and the resulting builds aren't reproducible.

# Gotchas
- `npm ci` DELETES node_modules and reinstalls clean. Faster than `install` for cold caches because it skips dependency resolution (it trusts the lockfile).
- `npm ci` REFUSES to run if package.json and package-lock.json are out of sync.
- Local `npm install` updates the lockfile to whatever it resolved.
- Always commit package-lock.json. Without it, every install is non-deterministic.

# Flags
- `--production` / `--omit=dev`: skip devDependencies (smaller install for prod images)
- `--ignore-scripts`: skip postinstall scripts (security)
- `--prefer-offline`: use cache before network

# Examples
- Dockerfile: `RUN npm ci --omit=dev`
- Local: `npm install lodash --save`
