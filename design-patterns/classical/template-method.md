---
slug: template-method
name: Template Method
category: classical
intent: Define the skeleton of an algorithm in a base method, deferring some steps to subclasses
references: GoF Template Method
---

# When to use
Multiple variants follow the same overall flow but differ in specific steps: a deployment script (clone → build → test → push → restart) where each step varies by target stack.

You want to enforce the OVERALL sequence while letting subclasses customize steps.

# When NOT to use
Subclasses end up overriding most steps — use strategy instead.

The 'algorithm' is one line and the override is the whole point — just use polymorphism directly.

# Structure
Base class defines a non-virtual template method that calls protected virtual primitives.  Subclasses override the primitives but not the template.

# Example
```csharp
public abstract class DeployStep {
    public async Task RunAsync(Ctx ctx) {  // template
        await PreFlight(ctx);
        await Stage(ctx);
        await Verify(ctx);
        await PostFlight(ctx);
    }
    protected abstract Task Stage(Ctx ctx);  // varies per subclass
    protected virtual Task PreFlight(Ctx ctx) => Task.CompletedTask;
    protected virtual Task Verify(Ctx ctx) => Task.CompletedTask;
    protected virtual Task PostFlight(Ctx ctx) => Task.CompletedTask;
}
```

# Relationships
Compare with strategy (strategy delegates the WHOLE algorithm; template method delegates STEPS).  Foundation of frameworks (Spring transactions, ASP.NET controller lifecycle).
