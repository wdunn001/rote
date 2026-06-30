---
slug: rollup-missing-native-binary-windows
title: Astro/Vite build fails on Windows with missing @rollup/rollup-win32-x64-msvc
hit_count: 1
token_cost: medium — burns a couple of failed build attempts before the cryptic MODULE_NOT_FOUND is diagnosed as the npm optional-dep bug
---

# Symptom

`astro build` (or any Vite/Rollup-backed build) throws on a Windows host:

```
Cannot find module '@rollup/rollup-win32-x64-msvc'
Require stack:
- node_modules/rollup/dist/native.js
  ... code: 'MODULE_NOT_FOUND'
```

The package is "installed" and `npm run <build>` otherwise resolves; only the native rollup binary is absent.

A sibling failure on the same host: `npm run build` -> `astro build` reports `'astro' is not recognized as an internal or external command` under the PowerShell runner, because `node_modules/.bin` shims are not resolved for the native-command spawn.

# Root cause

The well-known npm optional-dependency bug: rollup ships per-platform native binaries as `optionalDependencies`, and npm fails to install the correct one when `node_modules` was created under a different OS/arch than the host now running the build. Classic trigger: the tree was installed from a WSL/linux context (paths like `/mnt/h/...`) but the build runs on native Windows, so `@rollup/rollup-win32-x64-msvc` was never pulled in. Common where the real CI/deploy build runs in a linux container and only the occasional local verification build runs on Windows.

# Remedy

Install just the missing native binary without touching the manifests:

```bash
npm install @rollup/rollup-win32-x64-msvc --no-save --no-audit --no-fund
```

`--no-save` leaves `package.json` / `package-lock.json` unchanged (the container/linux install path stays authoritative). Then rebuild.

If `astro` (or any `.bin` shim) is not found under the PowerShell `npm run` invocation, call the package entrypoint directly instead of the shim:

```bash
node node_modules/astro/astro.js build      # Git Bash; .bin shims resolve here too
```

The heavier fix (only if you want the host to own its tree) is to delete `node_modules` and reinstall natively on Windows.

# Detection

`MODULE_NOT_FOUND` for any `@rollup/rollup-<platform>-<arch>` package, or any `@esbuild/<platform>` / `@swc/core-<platform>` analogue — all share this optional-dep failure mode. Smell: the build worked in CI/container but fails only on the dev host, and the host OS differs from where `node_modules` was last installed.

# See also

- [[rote]] skill
