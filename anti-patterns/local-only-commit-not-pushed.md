---
slug: local-only-commit-not-pushed
title: Claiming work is "done" when it's only committed locally
hit_count: 8
token_cost: critical — user discovers nothing shipped, asks "where is X?", trust eroded
---

# Symptom

Claude says "I've committed the fix" or "shipped". User checks the live site / their phone / the GitHub UI and the change is not there. Investigation shows the commit exists on `main` locally but was never pushed, OR was pushed but `npm run deploy` was never run.

# Root cause

"Done" is overloaded. Local commit, pushed commit, deployed commit are three different states. Without explicit verification of each step, it's easy to think the next step is the user's job.

# Remedy

**Hard rule:** A change is not done until ALL THREE of:

1. `git push origin main` succeeded
2. `npm run deploy` ran and reported success
3. The change is visible on the live URL OR in the freshly-deployed artifact

Always verify all three before saying "done" / "shipped" / "landed". For frontend changes, fetch the live page and confirm the new behavior is present. For API changes, hit the endpoint and confirm the new response shape. For mobile, install the rebuilt APK and confirm.

Use the deploy-verify script:

```bash
rote run verify-deploy --url https://app.acmefpv.com --expect-string "new-feature-marker"
```

(or `scripts/verify-deploy.sh` directly when CLI isn't available).

# Detection

Anytime you're about to type "shipped" / "deployed" / "done" — check:
- Has `git push` run successfully since the last commit?
- Has `npm run deploy` run?
- Has the deployed artifact been verified?

If any answer is "no" or "I don't know", finish those steps first.

# See also

- [[feedback-work-not-done-until-deployed]]
- [[host-direct-rebuild-bypassing-npm-run-deploy]]
