---
slug: singleton
name: Singleton
category: classical
intent: Ensure a class has only one instance and provide global access to it
references: GoF; Mark Seemann's 'Dependency Injection Principles'
---

# When to use
Genuinely-shared resources where multiple instances would corrupt state: a process-wide configuration loader after first read, a logging sink with a buffered file handle, an embedding model loaded once at startup.

State that the runtime ALREADY enforces as single-instance (a database connection pool managed by the framework, a sqlite db file with one writer at a time) and you just need a consistent access path.

# When NOT to use
DON'T use as a global-variable disguise.  Most "Singleton" classes in training-data code are global mutable state with extra ceremony.  The cost: untestable code, hidden coupling, race conditions, lifecycle that can't be controlled per test.

DON'T use for "just one of these for now" — use dependency injection.  The constructor takes the resource, the composition root wires it once.  You get one instance without the global access path.

# Structure
Private constructor + static instance + lazy initializer.  Modern variants use Lazy<T> (.NET), lazy_static / OnceCell (Rust), or a module-level instance (Python).  In Python the cleanest form is just a module-level variable initialized at import time.

# Example
```python
# Python: just use a module-level lazy attribute.
_model = None
def get_embed_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model
```

```csharp
// .NET: prefer DI singleton lifetime over the Singleton pattern itself.
services.AddSingleton<IEmbeddingModel, EmbeddingModel>();
```

# Relationships
Counterpart of dependency-injection (DI is usually better). See anti-pattern singleton-as-global-state. Composes with factory-method when the resource is expensive to build.
