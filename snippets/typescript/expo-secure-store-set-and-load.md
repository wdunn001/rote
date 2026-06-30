---
slug: expo-secure-store-set-and-load
name: expo-secure-store SET + LOAD pair
language: typescript
applies_patterns: secret-handling
applies_technologies: 
references: 
---

# When to use
Persisting device-side secrets in the Acme companion: device cert
private key, OIDC tokens, vault values that must survive app restarts.

# When NOT to use
Non-sensitive config (AsyncStorage is simpler).

Cross-device sync needed (SecureStore is device-only by design).

# Placeholders
- KEY_NAME: the storage key constant (example: KEY_DEVICE_PRIVATE_KEY_PEM)
- KEY_DESC: human-readable description for errors (example: device cert private key)

# Snippet
```typescript
import * as SecureStore from 'expo-secure-store';

export const ${KEY_NAME} = '${KEY_NAME}';

export async function set${KEY_NAME}(value: string): Promise<void> {
    try {
        await SecureStore.setItemAsync(${KEY_NAME}, value, {
            keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
        });
    } catch (err) {
        throw new Error(`failed to persist ${KEY_DESC}: ${err}`);
    }
}

export async function load${KEY_NAME}(): Promise<string | null> {
    return SecureStore.getItemAsync(${KEY_NAME});
}
```

# Example expansion
See apps/companion/src/identity/deviceCert.ts.
