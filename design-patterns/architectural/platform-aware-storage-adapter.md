---
slug: platform-aware-storage-adapter
name: Platform-aware adapter — thin shim that re-exports the same API across platforms
category: architectural
intent: Hide platform-specific storage / sensor / I/O differences behind a stable API so the rest of the codebase can stay portable
references: |
  Real-world: apps/companion/src/auth/secureStoreAdapter.ts in example-app.
  React Native's Platform.OS pattern; Capacitor / Cordova plugin adapters.
---

# When to use

Your cross-platform codebase (React Native + web, Electron, Capacitor, Cordova) imports a module that works on some platforms and silently no-ops or throws on others.  Direct imports leak the platform mismatch into every caller; tests written on the native platform pass while the other platform is silently broken.

Common case: `expo-secure-store` on iOS/Android (Keystore-backed) vs web (no-op).  Same trap exists for `expo-haptics`, `expo-task-manager`, `expo-keep-awake`, `expo-camera` web fallback.

# When NOT to use

The module already has a proper platform-conditional implementation upstream (e.g. `react-native-localize` which has a web polyfill).  Pure JS modules that work on every platform.  Modules where the trade-off requires per-callsite decisions (don't hide behind a one-size-fits-all shim).

# Structure

A single file under `src/auth/` (or wherever the module's domain belongs) that:

1. Re-exports types from the upstream module so callers don't need to re-import them.
2. Branches on `Platform.OS` (or `typeof window`) inside each public method.
3. Delegates to the upstream module on supported platforms.
4. Implements a fallback on unsupported platforms (or throws with a clear message if no fallback makes sense).
5. Documents the trade-off the fallback accepts.

```ts
// src/auth/secureStoreAdapter.ts
import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';

export type SecureStoreOptions = SecureStore.SecureStoreOptions;

// Exposed so callers can log it at boot if the trade-off matters in their flow.
export const IS_LOCAL_STORAGE_FALLBACK: boolean = Platform.OS === 'web';

export async function setItemAsync(key: string, value: string, options?: SecureStoreOptions): Promise<void> {
  if (Platform.OS === 'web') {
    if (typeof globalThis.localStorage === 'undefined') return;
    globalThis.localStorage.setItem(key, value);
    return;
  }
  await SecureStore.setItemAsync(key, value, options);
}

export async function getItemAsync(key: string, options?: SecureStoreOptions): Promise<string | null> {
  if (Platform.OS === 'web') {
    if (typeof globalThis.localStorage === 'undefined') return null;
    return globalThis.localStorage.getItem(key);
  }
  return await SecureStore.getItemAsync(key, options);
}

export async function deleteItemAsync(key: string, options?: SecureStoreOptions): Promise<void> {
  if (Platform.OS === 'web') {
    if (typeof globalThis.localStorage === 'undefined') return;
    globalThis.localStorage.removeItem(key);
    return;
  }
  await SecureStore.deleteItemAsync(key, options);
}
```

Then enforce the rule with a grep — direct imports of the upstream module from anywhere except the adapter are bugs.

# Migration

1. Write the adapter that mirrors the upstream API exactly.
2. Find every direct import: `grep -rln "from 'expo-secure-store'" src/`.
3. Rewrite each to `from '<relative>/auth/secureStoreAdapter'`.
4. Add a lint rule or pre-commit grep that blocks new direct imports.

# Trade-off discipline

Document the trade-off in the adapter file's banner: what's lost on the fallback path?  For SecureStore on web, you're trading Keychain/Keystore hardware isolation for "as secure as the origin" localStorage.  Acceptable for desktop wrappers and beta builds; production secret storage on desktop needs a stronger fallback (Tauri Stronghold, OS keyring bridge).

# Related

- [[expo-secure-store-web-noop]] — the bug class this pattern fixes.
- [[expo-module-web-noop-trap]] — broader audit recommendation.

# Real-world hit

Shipped on `example-app` 2026-06-04 commit `7e9e2dbc`, fixing the inescapable-OIDC bug on the Tauri desktop companion.
