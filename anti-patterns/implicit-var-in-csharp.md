---
slug: implicit-var-in-csharp
title: Implicit `var` declarations in example-app C#
hit_count: 6
token_cost: low per-instance but high cumulative — every PR review picks them up, every implicit `var` is a regression of the codebase rule
---

# Symptom

C# code in `example-app` (or any new C# code added to the repo) uses `var foo = ...` instead of the explicit type. Reviewer asks for a rewrite.

# Root cause

Project rule: explicit types make code readable on GitHub mobile, in PR diffs, and in long methods without needing an IDE for inlay hints. Auto-formatters that "fix" `var` to explicit type are landing the rule, not noise — DO NOT revert them.

# Remedy

Always declare with the explicit type:

```csharp
// good
List<Drone> drones = await _droneRepo.ListAsync();
DroneCommand command = MapToCommand(req);

// bad
var drones = await _droneRepo.ListAsync();
var command = MapToCommand(req);
```

For LINQ chains with anonymous types, name them or refactor away from the anonymous type. For long generic returns, accept the verbosity — it's the price of clarity.

# Detection

Run `grep -rn 'var ' src/Acme.*/` — every hit is a violation. Auto-fix by hand or via Roslyn analyzer.

# See also

- [[feedback-no-implicit-var]]
