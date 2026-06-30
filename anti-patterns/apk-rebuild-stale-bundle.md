---
slug: apk-rebuild-stale-bundle
title: Gradle skips bundleReleaseJsAndAssets — APK ships stale Hermes bytecode
hit_count: 1
token_cost: high — full APK build wasted, change appears not to have shipped, hours of "why isn't this taking effect"
---

# Symptom

You edit JS/TS in `apps/companion/`, run `eas build` or `./gradlew assembleRelease`, install the new APK on a device, and the change **does not appear**. Hermes bytecode at `android/app/build/generated/assets/createBundleReleaseJsAndAssets/index.android.bundle` is byte-identical to the prior build. Grep on the bundle returns 0 matches even when the source clearly contains the string.

# Root cause

Gradle's `bundleReleaseJsAndAssets` task is incremental and the inputs hash misses some changes (especially when only sub-package source changed but the touched workspace package's `package.json` didn't bump). The merged assets directory still contains the prior bundle, so the APK packs the stale bytecode. Hermes bytecode is also not greppable as strings — confirming "is the change in here" via `grep` on the bundle is unreliable.

# Remedy (deterministic)

Nuke the four caches that hide the staleness, then rebuild:

```bash
cd apps/companion/android
rm -rf app/build/generated/assets/createBundleReleaseJsAndAssets/
rm -rf app/build/intermediates/assets/release/createReleaseAssets/
rm -rf app/build/intermediates/merged_assets/release/
rm -rf ../node_modules/.cache
./gradlew clean assembleRelease
```

To **verify** the change is actually in the new bundle, do NOT grep the bundle — grep the **sourcemap** instead:

```bash
grep -c "MY_NEW_STRING" android/app/build/generated/sourcemaps/react/release/index.android.bundle.map
```

# Detection

If you've installed a fresh APK and the change isn't there, **stop trying alternate code paths** and verify the bundle freshness via the sourcemap grep above. Don't burn 20 minutes assuming the code is wrong.
