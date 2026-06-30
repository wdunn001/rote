---
slug: mediator
name: Mediator
category: classical
intent: Replace many-to-many direct coupling between a set of objects with a central mediator they each talk to, so interaction logic lives in one place and the participants stay independent and reusable.
references: Gamma, Helm, Johnson, Vlissides, "Design Patterns" (GoF, 1994), Mediator. Canonical metaphor: an air-traffic-control tower coordinating planes that never talk to each other directly.
---

# When to use

A set of objects communicate in well-defined but complex ways, and the resulting web of references is hard to follow or change.

Reuse of an object is hard because it refers to and talks with many others.

Behavior distributed across several classes should be customizable in one place without subclassing all of them.

# When NOT to use

Only two parties are involved; just let them call each other.

Communication is naturally a broadcast with no coordination logic; use [[observer]] or an event bus instead.

The mediator accumulates every rule in the system and becomes a god-object; split it or push logic back to the colleagues.

# Structure

A Mediator interface declares how colleagues notify it. A ConcreteMediator coordinates the colleagues and holds the interaction logic. Each Colleague holds a reference to the mediator (not to other colleagues) and notifies it of events; the mediator decides who else to update.

# Example

A dialog box where each widget reports changes to the mediator, which enables/disables and updates the others. An air-traffic tower where planes request and receive clearance from the tower rather than negotiating with each other.

# Relationships

The base GoF pattern that [[stenographic-mediator]] extends and automates with an AI in the mediator seat. Contrast [[observer]] (broadcast, no central coordinator). The distributed/remote cousin is a Broker. Often carries [[command]] objects between colleagues and can route them via [[chain-of-responsibility]]. Centralized shared state relates it to [[blackboard]] and [[canonical-data-model]].
