---
slug: abstract-factory
name: Abstract Factory
category: classical
intent: Create FAMILIES of related products without coupling clients to their concrete classes
references: GoF Abstract Factory
---

# When to use
You need to swap an entire family of related objects together — e.g., a UI toolkit (Buttons + Menus + Dialogs that must match), a database driver family (Connection + Command + DataReader), a protocol family (Encoder + Decoder + Framer that share wire-format assumptions).

The products MUST be compatible with each other and you don't want clients to mix-and-match wrong variants.

# When NOT to use
Only one product family exists — overengineered.

The 'families' don't have real coupling between products — use independent factories instead.

# Structure
AbstractFactory declares create methods for each product type.  Concrete factories return the matching variant family.

# Example
```typescript
interface ProtocolFactory {
  createEncoder(): IEncoder;
  createDecoder(): IDecoder;
  createFramer(): IFramer;
}
class MavlinkV2Factory implements ProtocolFactory { /* returns matching v2 trio */ }
class MspFactory implements ProtocolFactory { /* returns matching MSP trio */ }
```

# Relationships
Bigger version of factory-method.  Composes with strategy (each product is a strategy slot).
