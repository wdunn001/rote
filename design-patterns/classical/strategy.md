---
slug: strategy
name: Strategy
category: classical
intent: Define a family of interchangeable algorithms; pick one at runtime
references: GoF Strategy; lives in mz-pid-tuner gcs_link Strategy + Factory + Registry trio
---

# When to use
Multiple algorithms differ but share an interface.  Examples: per-firmware MAVLink commanders (ArduPilot vs PX4 vs INav), per-tenant resilience policies, per-codec compression strategies, per-platform GCS link.

The choice is deferred to runtime, configured per tenant, or selected by capability/feature flag rather than baked in at compile time.

# When NOT to use
Only one variant exists today and "future variants" are speculative — premature indirection.

The variants share so much state that you've got a parameterized algorithm, not separate strategies.  Use parameters.

You're tempted to add a fifth strategy that violates Liskov substitution (one strategy needs extra context the others don't).  Refactor to chain-of-responsibility or visitor.

# Structure
Context holds a reference to a Strategy interface.  Concrete strategies implement it.  Context delegates the operation.

# Example
```typescript
interface FirmwareCommander {
  encodeFlyToHere(target: GeoPoint): Uint8Array;
  encodeArm(): Uint8Array;
}
class ArduPilotCommander implements FirmwareCommander { /* ... */ }
class Px4Commander implements FirmwareCommander { /* ... */ }
class INavCommander implements FirmwareCommander { /* ... */ }

const cmd: FirmwareCommander = pickCommander(drone.firmwareFamily);
sendFrame(cmd.encodeFlyToHere(target));
```

# Relationships
Composes with factory-method (factory creates the strategy).  Alternative to chain-of-responsibility (CoR walks handlers; Strategy picks one).  Often paired with circuit-breaker (the breaker is itself a strategy wrapping the call).
