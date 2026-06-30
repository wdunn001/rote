---
slug: cross-repo-contract-drift-guard
name: Cross-Repo Contract Drift Guard
category: architectural
intent: Keep a contract that is hand-mirrored across several repos from silently diverging, via one source-of-truth file plus a check script that asserts a version constant and the canonical tokens match every mirror
references: mz-halow-bridge/scripts/check_contract_sync.py (2026-06)
---

# When to use
A contract (a wire header, a token vocabulary, an enum) lives canonically in one repo but is hand-copied or re-implemented in others (a C header vendored into firmware, a TS type mirroring it in two client apps, a C# catalog on the backend).

The repos advance on independent mains, so the copies WILL drift as people touch them.

You want a cheap, deterministic guard, not a build-system coupling.

Example: `mz_halow_link.h` (source of truth) vendored into mz-pid-tuner, mirrored by `halow-descriptor.ts` x2 and `IngestBearer.cs`. A checker asserts `MZ_HALOW_CONTRACT_VERSION` matches the vendored header and that `halow` / `halow-mavlink` / `MZ_HAS_GCS_LINK_HALOW` appear in each mirror.

# When NOT to use
The contract is genuinely shared via a package (npm/NuGet/git-subtree) so there is one physical copy already.

There is only one consumer (no mirror to drift).

The contract changes so often that a published package with semver is the right tool instead.

# Structure
1. One canonical file with an explicit version constant (`#define X_CONTRACT_VERSION N`).
2. A check script in the source-of-truth repo that:
   - reads the canonical version,
   - compares it to each vendored copy (skip-with-note if a sibling is absent, so it still runs standalone in CI),
   - asserts the canonical string tokens are present in each mirror file.
   - exits non-zero on any mismatch.
3. Siblings auto-resolved as `../<repo>`, overridable by flag.
4. Wire it into pre-commit / CI in every consumer; bump the version constant on any breaking change.

# Notes
Bump-on-breaking-change is the discipline that makes the version assert meaningful. The token check catches the subtler drift (a renamed enum value, a changed wire string) that a version bump alone would miss.
