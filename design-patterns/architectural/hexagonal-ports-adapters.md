---
slug: hexagonal-ports-adapters
name: Hexagonal (Ports & Adapters)
category: architectural
intent: Isolate the application core from external concerns via interfaces (ports) and replaceable implementations (adapters)
references: Alistair Cockburn 'Hexagonal Architecture'
---

# When to use
The application has multiple input mechanisms (HTTP API, CLI, queue worker) and multiple output mechanisms (Postgres, blob storage, email, MQTT).

You want tests that swap out infra for fakes without rewriting the application.

You want the freedom to swap one provider for another (AWS S3 → Azure Blob) without rewriting business code.

# When NOT to use
The 'core' is genuinely glue code over one provider — adding ports just adds indirection.

Adapters are shipped as the canonical thing (no expectation of swapping) — the port becomes a noise interface.

# Structure
Application core defines PORTS (Domain or Application interfaces: IEmailSender, IClock, IDroneRepository).  ADAPTERS implement ports against concrete tech.  Composition root wires the adapters.  Tests substitute fakes.

# Example
```csharp
// Port (Domain)
public interface IEmailSender { Task SendAsync(EmailMessage m, CancellationToken ct); }

// Adapter (Infrastructure)
public class MicrosoftGraphEmailSender : IEmailSender { /* ... */ }

// No-op adapter (for local dev without Graph creds)
public class NoOpEmailSender : IEmailSender { public Task SendAsync(...) => Task.CompletedTask; }

// Test fake
public class CapturingEmailSender : IEmailSender { public List<EmailMessage> Sent = new(); /* ... */ }
```

# Relationships
Identical idea to clean-architecture, different visualization.  Foundation of dependency-injection.  Pairs with adapter pattern (every implementation IS an Adapter).  See backend-ports-and-testing.mdc in Acme.
