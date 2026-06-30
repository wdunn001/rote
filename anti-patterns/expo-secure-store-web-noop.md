---
slug: expo-secure-store-web-noop
title: expo-secure-store is a silent no-op on Platform.OS === 'web'
category: react-native
cost: ~3 days of "inescapable OIDC login" user reports before the root cause is identified; ~1 hour to rewire every callsite once you know
---

# Symptom

A React Native / Expo codebase that's historically iOS+Android starts shipping a Tauri desktop wrapper or an `npx expo export --platform web` bundle.  Users on the web/desktop build see an "inescapable" auth redirect on every cold load — sign in succeeds, app works for the session, reload → signed-out again.  The code path that should hydrate the session from `expo-secure-store` is being called and is "succeeding" — but every read returns null.

# Root cause

`expo-secure-store` v17 has no web implementation.  `setItemAsync` writes nowhere; `getItemAsync` returns `null`.  TypeScript types are identical across all platforms, so there's no compile-time signal that the web target is broken.  Older versions threw at runtime; current versions silently no-op.  Any persisted state — auth tokens, device certs, identity snapshots, PKCE state, config — is discarded on every reload.

# Remedy

Wrap `expo-secure-store` behind a thin platform-aware adapter and re-wire every caller through the adapter (NOT direct `expo-secure-store` imports).  The adapter delegates to real SecureStore on `Platform.OS in {ios, android}` and falls back to `localStorage` on web with the same key namespace.

```ts
// src/auth/secureStoreAdapter.ts
import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';

export type SecureStoreOptions = SecureStore.SecureStoreOptions;

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

Then re-wire every direct importer:

```
grep -rln "from 'expo-secure-store'" apps/companion/src apps/companion/app
# replace each `from 'expo-secure-store'` with `from '<relative>/auth/secureStoreAdapter'`
```

Document the trade-off in the adapter file: on web the storage is "as secure as the origin" (or "as secure as the Tauri app sandbox" inside Tauri), NOT hardware-isolated.  Acceptable for beta / desktop wrappers; when production-grade isolation is needed on desktop, upgrade the web branch to Tauri Stronghold or equivalent.

# How it slipped past

- The companion was iOS+Android only historically; Keystore / Keychain worked correctly there.
- The Tauri wrapping + Expo-for-Web export landed without auditing the storage layer.
- No CI matrix exercises the web build.
- TS types don't differentiate platforms.

# Other Expo modules at risk

Same trap pattern likely on: `expo-keep-awake`, `expo-task-manager`, `expo-camera`, `expo-background-fetch`, `expo-haptics`, `expo-notifications` (partial), `expo-local-authentication` (partial — falls back to passcode on most platforms but no hardware on web).

# Related

- [[platform-aware-storage-adapter]] — the pattern shape.
- [[expo-module-web-noop-trap]] — process recommendation to audit all native-only Expo modules.
- `stacks/success/acme-companion-tauri-web-export` if/when we record the Tauri stack.

# Real-world hit

Shipped fix on `example-app` 2026-06-04 commit `7e9e2dbc`.  Seven callsites rewired (`secureTokenStore`, `CompanionDeviceIdentity`, `configStorage`, `registerDevice`, `companionEnrollmentMigration`, `device-enrollment-api`, `mqtt-public-broker`).  User report symptom: "inescapable OIDC login all the time even after the certificate change."
