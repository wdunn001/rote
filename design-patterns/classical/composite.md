---
slug: composite
name: Composite
category: classical
intent: Treat individual objects and compositions of objects uniformly
references: GoF Composite
---

# When to use
You have a tree structure where leaves and branches should respond to the same operations: file system, UI components, Fleet-as-Swarm (Swarm IS a composite of Drone leaves).

Operations should recurse naturally through the structure.

# When NOT to use
The structure is flat (just a list) — composite is for trees, not collections.

Leaf and Composite need genuinely different interfaces — forcing them into the same shape produces uniformly-bad code.

# Structure
Component (abstract or interface) — both Leaf and Composite implement it.  Composite holds children and forwards operations.

# Example
```csharp
public abstract class FleetNode {
    public abstract IEnumerable<Drone> AllDrones();
}
public class Drone : FleetNode {
    public override IEnumerable<Drone> AllDrones() => new[] { this };
}
public class Swarm : FleetNode {
    private readonly List<FleetNode> _children = new();
    public override IEnumerable<Drone> AllDrones() => _children.SelectMany(c => c.AllDrones());
}
```

# Relationships
Foundational for hierarchical aggregates.  Pairs with visitor (operations across a composite tree).  Used in acme Fleet-as-Swarm and in firmware FleetHome (multi-source composite).
