---
slug: factory-method
name: Factory Method
category: classical
intent: Defer instantiation to a method, letting subclasses or runtime decide which concrete type to create
references: GoF Factory Method
---

# When to use
You know you need 'an X' but the concrete X depends on runtime context: which DB driver, which protocol parser, which firmware commander.

Constructor signatures across the variants diverge — factory hides the differences behind a uniform call.

Lazy initialization with non-trivial wiring (resolve config, look up registered strategies, allocate resources).

# When NOT to use
Plain old `new Foo()` works and the type is genuinely fixed.  Don't add a factory because 'one day we might.'

The factory's only job is to call one constructor — that's a static method that's actively misleading.

# Structure
Creator (abstract or interface) declares the factory method.  ConcreteCreators override it.  Or a static / module-level factory function that switches on input.

# Example
```csharp
public interface IFirmwareCommander { /* ... */ }

public static class FirmwareCommanderFactory {
    public static IFirmwareCommander Create(FirmwareFamily family) => family switch {
        FirmwareFamily.ArduPilot => new ArduPilotCommander(),
        FirmwareFamily.PX4       => new Px4Commander(),
        FirmwareFamily.INav      => new INavCommander(),
        _ => throw new NotSupportedException($"unsupported firmware: {family}")
    };
}
```

# Relationships
Pairs with strategy (factory produces the strategy).  See abstract-factory when you need families of related products.  Often composes with registry-pattern for plug-in-style discovery.
