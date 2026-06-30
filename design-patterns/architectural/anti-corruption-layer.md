---
slug: anti-corruption-layer
name: Anti-Corruption Layer (ACL)
category: architectural
intent: Insert a translation layer between two domains (typically a clean model and a legacy/external/third-party one) so each keeps its own language and concepts, and neither side's model leaks into and corrupts the other.
references: Eric Evans, "Domain-Driven Design" (2003), Anti-Corruption Layer. Composes a Facade + Adapter + Translator at a bounded-context boundary.
---

# When to use

You integrate with a legacy, external, or vendor model you do not control and do not want shaping your own.

You are migrating off a legacy system incrementally and need the new model insulated during the transition.

Two bounded contexts have genuinely different meanings for similar-looking terms.

# When NOT to use

Both sides are one team sharing one model; the translation overhead buys nothing.

The external model is already clean, stable, and aligned with yours.

A throwaway or one-off integration where insulation will never pay off.

# Structure

A boundary layer that speaks the external dialect outward and the local dialect inward. Internally: a Facade over the foreign system, Adapters that conform its interface, and Translators that convert between the foreign model and the local one. Nothing foreign passes the layer untranslated.

# Example

Wrapping a payments vendor's API so your domain only ever sees your own Money and Order types. In [[stenographic-mediator]], the mechanic that translates each expert discipline's dialect so engineering's "federation" reaches a stakeholder as "should outside businesses log in with their own credentials," without either vocabulary leaking.

# Relationships

A boundary-enforcing application of [[canonical-data-model]] built from [[adapter]] and a Facade. Protects a [[domain-driven-aggregate]] from upstream rot. A core building block of [[stenographic-mediator]].
