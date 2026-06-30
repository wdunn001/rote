---
slug: builder
name: Builder
category: classical
intent: Construct a complex object step-by-step, separating construction from representation
references: GoF Builder; Joshua Bloch 'Effective Java' Item 2
---

# When to use
The thing being built has many optional fields and constructor-overload combinatorics would explode.

Construction is multi-step with validation between steps (validate auth, then connection, then schema, then ready).

The same construction process should produce different output forms (a SQL query as text vs an AST).

# When NOT to use
Object has 3-4 fields — just use a constructor or record literal.

Validation can happen in the constructor — adding a builder is ceremony.

# Structure
Builder holds intermediate state; setters return self for fluent chaining; build() validates + emits the final object.

# Example
```typescript
const config = new DeployConfigBuilder()
  .host("edge-host")
  .user("edge-host")
  .remoteDir("/srv/app")
  .composeBuild({serial: true})
  .skipAuthentikRecreate()
  .build();
```

# Relationships
Pairs with prototype when builders share a base configuration.  Alternative to factory when construction is multi-step rather than discriminator-based.
