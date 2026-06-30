---
slug: mavlink-discriminated-union-typescript
name: MAVLink DroneCommand discriminated union (TS)
language: typescript
applies_patterns: command, strategy
applies_technologies: 
references: 
---

# When to use
Defining a verb set where each verb has different payload shape and the
encoder/dispatcher needs exhaustive case handling.  Used heavily in
packages/mavlink-control.

# When NOT to use
All verbs share the same payload shape — use a regular interface + verb enum.

The set is huge (50+ verbs) — consider a class-per-verb design instead.

# Placeholders
- UNION_NAME: the discriminated-union type name (example: DroneCommand)
- DISCRIM: the discriminator field name (example: kind)

# Snippet
```typescript
export type ${UNION_NAME} =
    | { ${DISCRIM}: 'arm' }
    | { ${DISCRIM}: 'disarm' }
    | { ${DISCRIM}: 'flyToHere', target: GeoPoint, ned?: NedOffset }
    | { ${DISCRIM}: 'follow', leader: SystemId, distance?: number }
    | { ${DISCRIM}: 'rtl' }
    | { ${DISCRIM}: 'uploadMission', plan: FlightPlan };

export function dispatch${UNION_NAME}(
    cmd: ${UNION_NAME},
    handler: { [K in ${UNION_NAME}["${DISCRIM}"]]: (c: Extract<${UNION_NAME}, { ${DISCRIM}: K }>) => Uint8Array }
): Uint8Array {
    return (handler as any)[cmd.${DISCRIM}](cmd);
}
```

# Example expansion
See packages/mavlink-control/src/DroneCommand.ts.
