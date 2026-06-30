#!/usr/bin/env python3
"""
script: seed-design-patterns-and-technologies.py
purpose: Generate the curated initial markdown for the design-patterns and
         technologies catalogs.  Idempotent — overwrites only when content
         changes; preserves use_count etc. because those live in the DB,
         not the files.
family: seed-design-patterns-and-technologies
environment: cross-python
inputs: --root <path>   default /path/to/rote/
        --dry-run       print what would be written
outputs: per-file lines
exit 0 success, 5 bad args

When you add new patterns or technologies, do it as standalone markdown
files in design-patterns/<category>/<slug>.md or
technologies/<category>/<slug>.md and the API auto-indexes them.  This
script is for the INITIAL seed and for re-establishing the catalog on a
fresh clone.
added: 2026-06-03
"""
from __future__ import annotations
import argparse
import sys
import textwrap
from pathlib import Path


# ---------------------------------------------------------------------------
# DESIGN PATTERNS
# ---------------------------------------------------------------------------
DESIGN_PATTERNS: list[dict] = [
    # ============ CLASSICAL ============
    {
        "slug": "singleton",
        "name": "Singleton",
        "category": "classical",
        "intent": "Ensure a class has only one instance and provide global access to it",
        "when_to_use": """
Genuinely-shared resources where multiple instances would corrupt state: a process-wide configuration loader after first read, a logging sink with a buffered file handle, an embedding model loaded once at startup.

State that the runtime ALREADY enforces as single-instance (a database connection pool managed by the framework, a sqlite db file with one writer at a time) and you just need a consistent access path.
""",
        "when_not_to_use": """
DON'T use as a global-variable disguise.  Most "Singleton" classes in training-data code are global mutable state with extra ceremony.  The cost: untestable code, hidden coupling, race conditions, lifecycle that can't be controlled per test.

DON'T use for "just one of these for now" — use dependency injection.  The constructor takes the resource, the composition root wires it once.  You get one instance without the global access path.
""",
        "structure": """
Private constructor + static instance + lazy initializer.  Modern variants use Lazy<T> (.NET), lazy_static / OnceCell (Rust), or a module-level instance (Python).  In Python the cleanest form is just a module-level variable initialized at import time.
""",
        "example_code": """
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
""",
        "relationships": "Counterpart of dependency-injection (DI is usually better). See anti-pattern singleton-as-global-state. Composes with factory-method when the resource is expensive to build.",
        "references": "GoF; Mark Seemann's 'Dependency Injection Principles'",
    },
    {
        "slug": "strategy",
        "name": "Strategy",
        "category": "classical",
        "intent": "Define a family of interchangeable algorithms; pick one at runtime",
        "when_to_use": """
Multiple algorithms differ but share an interface.  Examples: per-firmware MAVLink commanders (ArduPilot vs PX4 vs INav), per-tenant resilience policies, per-codec compression strategies, per-platform GCS link.

The choice is deferred to runtime, configured per tenant, or selected by capability/feature flag rather than baked in at compile time.
""",
        "when_not_to_use": """
Only one variant exists today and "future variants" are speculative — premature indirection.

The variants share so much state that you've got a parameterized algorithm, not separate strategies.  Use parameters.

You're tempted to add a fifth strategy that violates Liskov substitution (one strategy needs extra context the others don't).  Refactor to chain-of-responsibility or visitor.
""",
        "structure": "Context holds a reference to a Strategy interface.  Concrete strategies implement it.  Context delegates the operation.",
        "example_code": """
```typescript
interface FirmwareCommander {
  encodeFlyToHere(target: GeoPoint): Uint8Array;
  encodeArm(): Uint8Array;
}
class ArduPilotCommander implements FirmwareCommander { /* ... */ }
class Px4Commander implements FirmwareCommander { /* ... */ }
class INavCommander implements FirmwareCommander { /* ... */ }

const cmd: FirmwareCommander = pickCommander(drone.firmwareFamily);
sendFrame(cmd.encodeFlyToHere(target));
```
""",
        "relationships": "Composes with factory-method (factory creates the strategy).  Alternative to chain-of-responsibility (CoR walks handlers; Strategy picks one).  Often paired with circuit-breaker (the breaker is itself a strategy wrapping the call).",
        "references": "GoF Strategy; lives in mz-pid-tuner gcs_link Strategy + Factory + Registry trio",
    },
    {
        "slug": "factory-method",
        "name": "Factory Method",
        "category": "classical",
        "intent": "Defer instantiation to a method, letting subclasses or runtime decide which concrete type to create",
        "when_to_use": """
You know you need 'an X' but the concrete X depends on runtime context: which DB driver, which protocol parser, which firmware commander.

Constructor signatures across the variants diverge — factory hides the differences behind a uniform call.

Lazy initialization with non-trivial wiring (resolve config, look up registered strategies, allocate resources).
""",
        "when_not_to_use": """
Plain old `new Foo()` works and the type is genuinely fixed.  Don't add a factory because 'one day we might.'

The factory's only job is to call one constructor — that's a static method that's actively misleading.
""",
        "structure": "Creator (abstract or interface) declares the factory method.  ConcreteCreators override it.  Or a static / module-level factory function that switches on input.",
        "example_code": """
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
""",
        "relationships": "Pairs with strategy (factory produces the strategy).  See abstract-factory when you need families of related products.  Often composes with registry-pattern for plug-in-style discovery.",
        "references": "GoF Factory Method",
    },
    {
        "slug": "abstract-factory",
        "name": "Abstract Factory",
        "category": "classical",
        "intent": "Create FAMILIES of related products without coupling clients to their concrete classes",
        "when_to_use": """
You need to swap an entire family of related objects together — e.g., a UI toolkit (Buttons + Menus + Dialogs that must match), a database driver family (Connection + Command + DataReader), a protocol family (Encoder + Decoder + Framer that share wire-format assumptions).

The products MUST be compatible with each other and you don't want clients to mix-and-match wrong variants.
""",
        "when_not_to_use": """
Only one product family exists — overengineered.

The 'families' don't have real coupling between products — use independent factories instead.
""",
        "structure": "AbstractFactory declares create methods for each product type.  Concrete factories return the matching variant family.",
        "example_code": """
```typescript
interface ProtocolFactory {
  createEncoder(): IEncoder;
  createDecoder(): IDecoder;
  createFramer(): IFramer;
}
class MavlinkV2Factory implements ProtocolFactory { /* returns matching v2 trio */ }
class MspFactory implements ProtocolFactory { /* returns matching MSP trio */ }
```
""",
        "relationships": "Bigger version of factory-method.  Composes with strategy (each product is a strategy slot).",
        "references": "GoF Abstract Factory",
    },
    {
        "slug": "builder",
        "name": "Builder",
        "category": "classical",
        "intent": "Construct a complex object step-by-step, separating construction from representation",
        "when_to_use": """
The thing being built has many optional fields and constructor-overload combinatorics would explode.

Construction is multi-step with validation between steps (validate auth, then connection, then schema, then ready).

The same construction process should produce different output forms (a SQL query as text vs an AST).
""",
        "when_not_to_use": """
Object has 3-4 fields — just use a constructor or record literal.

Validation can happen in the constructor — adding a builder is ceremony.
""",
        "structure": "Builder holds intermediate state; setters return self for fluent chaining; build() validates + emits the final object.",
        "example_code": """
```typescript
const config = new DeployConfigBuilder()
  .host("edge-host")
  .user("edge-host")
  .remoteDir("/srv/app")
  .composeBuild({serial: true})
  .skipAuthentikRecreate()
  .build();
```
""",
        "relationships": "Pairs with prototype when builders share a base configuration.  Alternative to factory when construction is multi-step rather than discriminator-based.",
        "references": "GoF Builder; Joshua Bloch 'Effective Java' Item 2",
    },
    {
        "slug": "decorator",
        "name": "Decorator",
        "category": "classical",
        "intent": "Add behavior to an object dynamically by wrapping it, without modifying the wrapped type",
        "when_to_use": """
You want to compose orthogonal behaviors at runtime: logging + retry + cache + rate-limit around the same call.

The wrapped object shouldn't know it's being decorated (the wrapper preserves the original interface).

Examples: HttpClient handlers in .NET, middleware in web frameworks, Polly policy wrappers.
""",
        "when_not_to_use": """
Behaviors are static and known at design time — use inheritance or direct composition.

The decorator changes the interface (now it's an adapter, not a decorator).
""",
        "structure": "Decorator implements the same interface as the wrapped Component; holds a reference to it; delegates to it + adds behavior before/after.",
        "example_code": """
```csharp
// HttpClient handler chain — each handler decorates the next.
services.AddHttpClient<IFooClient, FooClient>()
    .AddHttpMessageHandler<RetryHandler>()
    .AddHttpMessageHandler<CircuitBreakerHandler>()
    .AddHttpMessageHandler<LoggingHandler>();
```
""",
        "relationships": "Foundation of middleware / pipeline patterns.  Pairs with chain-of-responsibility (which routes; decorator wraps).  Often used to implement resilience patterns (circuit-breaker, retry, timeout).",
        "references": "GoF Decorator",
    },
    {
        "slug": "adapter",
        "name": "Adapter",
        "category": "classical",
        "intent": "Convert one interface into another that clients expect",
        "when_to_use": """
Wrapping a third-party library so it implements YOUR interface (so you can swap libraries later).

Bridging legacy code into modern interfaces.

Implementing a port (Domain interface) with concrete tech (Infrastructure) — every Infrastructure adapter is the Adapter pattern.
""",
        "when_not_to_use": """
The interfaces are already compatible — direct call, no wrapper.

You're adapting MANY methods with deep mismatch — refactor toward a custom interface instead of bridging.
""",
        "structure": "Adapter holds a reference to the Adaptee and implements the Target interface by translating calls.",
        "example_code": """
```csharp
// Infrastructure adapter wrapping Graph API to satisfy the Domain IEmailSender port.
public class MicrosoftGraphEmailSender : IEmailSender {
    private readonly GraphServiceClient _graph;
    public Task SendAsync(EmailMessage m, CancellationToken ct) =>
        _graph.Users[...].SendMail.PostAsync(GraphFor(m), cancellationToken: ct);
}
```
""",
        "relationships": "Foundation of hexagonal-ports-adapters.  Different from decorator (adapter changes interface; decorator preserves it).",
        "references": "GoF Adapter; Cockburn 'Hexagonal Architecture'",
    },
    {
        "slug": "composite",
        "name": "Composite",
        "category": "classical",
        "intent": "Treat individual objects and compositions of objects uniformly",
        "when_to_use": """
You have a tree structure where leaves and branches should respond to the same operations: file system, UI components, Fleet-as-Swarm (Swarm IS a composite of Drone leaves).

Operations should recurse naturally through the structure.
""",
        "when_not_to_use": """
The structure is flat (just a list) — composite is for trees, not collections.

Leaf and Composite need genuinely different interfaces — forcing them into the same shape produces uniformly-bad code.
""",
        "structure": "Component (abstract or interface) — both Leaf and Composite implement it.  Composite holds children and forwards operations.",
        "example_code": """
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
""",
        "relationships": "Foundational for hierarchical aggregates.  Pairs with visitor (operations across a composite tree).  Used in acme Fleet-as-Swarm and in firmware FleetHome (multi-source composite).",
        "references": "GoF Composite",
    },
    {
        "slug": "chain-of-responsibility",
        "name": "Chain of Responsibility",
        "category": "classical",
        "intent": "Pass a request along a chain of handlers; each handler decides whether to handle it or forward",
        "when_to_use": """
Multiple potential handlers and the right one is determined at runtime: middleware, request routing, fallback chains, message routing.

The chain order matters and handlers know nothing of each other.

Examples: c2_router in mz-pid-tuner (try DeviceA MQTT → fall back to WiFi-TCP → return Unreachable), ASP.NET middleware pipeline.
""",
        "when_not_to_use": """
Exactly one handler will handle the request — use Strategy instead.

The chain is short (2 handlers) — direct if/else is clearer.

Handlers need to coordinate or share state — use mediator.
""",
        "structure": "Handler interface declares Handle(request).  Each ConcreteHandler decides: handle it, transform-and-pass-on, or pass-on unchanged.  Last handler returns a default or raises.",
        "example_code": """
```cpp
// mz-pid-tuner c2_router::send() walks Strategies best-to-worst
SendResult C2Router::send(PeerIdentity peer, const uint8_t* data, size_t n) {
    for (auto& strategy : strategies_) {
        SendResult r = strategy.send(peer, data, n);
        if (r != SendResult::Unreachable) return r;
    }
    return SendResult::Unreachable;
}
```
""",
        "relationships": "Pairs with strategy (each handler IS a strategy).  Used in routers, middleware, fallback policies.  Often composed with circuit-breaker (open breaker fast-fails to next handler).",
        "references": "GoF Chain of Responsibility",
    },
    {
        "slug": "command",
        "name": "Command",
        "category": "classical",
        "intent": "Encapsulate a request as an object — parameters, receiver, action — so it can be queued, logged, undone, replayed",
        "when_to_use": """
Operations need to be persisted (audit log, event sourcing, undo/redo).

Operations need to be deferred (queue, schedule, batch).

You want to send operations over a wire (a wire format = serialized commands).

Examples: DroneCommand discriminated-union in mz packages, CoT activity tracker, replay-able CQRS commands.
""",
        "when_not_to_use": """
Operations are synchronous, never persisted, never undone — direct method calls are simpler.

You're using Command as a fancy lambda — just use a lambda.
""",
        "structure": "Command interface declares Execute().  Concrete commands hold all parameters + reference to receiver.  Invoker triggers execute (synchronously or queued).",
        "example_code": """
```typescript
type DroneCommand =
  | { kind: 'arm' }
  | { kind: 'flyToHere', target: GeoPoint, ned?: NedOffset }
  | { kind: 'follow', leader: SystemId, distance?: number }
  | { kind: 'rtl' };

// Wire-format = serialized command; replay = re-execute
function execute(cmd: DroneCommand) { /* discriminated dispatch */ }
```
""",
        "relationships": "Foundation of CQRS (commands separate from queries).  Foundation of event-sourcing (the event log IS the sequence of executed commands).  Pairs with outbox-pattern for reliable cross-system command propagation.",
        "references": "GoF Command",
    },
    {
        "slug": "observer",
        "name": "Observer",
        "category": "classical",
        "intent": "Define a one-to-many dependency so when one object changes state, dependents are notified automatically",
        "when_to_use": """
Reactive UIs: state change drives view re-render.

Domain event broadcasting: a sale completed → notify inventory, billing, audit, analytics independently.

Realtime subscriptions: a SignalR hub broadcasts to N clients; an MQTT topic publishes to N subscribers.
""",
        "when_not_to_use": """
The notification is a one-shot — use a callback / Promise.

Observers form cycles or need ordered execution — use a proper event-bus with ordering guarantees.

You actually need persistent subscription semantics across crashes — use queue-based / outbox patterns.
""",
        "structure": "Subject maintains a list of Observers.  Observers register / unregister.  On state change, Subject calls Update on each observer.",
        "example_code": """
```csharp
// SignalR is observer at scale — Update = SendAsync.
public class TakActivityHub : Hub {
    public async Task SubscribeCompany(string companyId) {
        await Groups.AddToGroupAsync(Context.ConnectionId, $"company:{companyId}");
    }
}

// Publisher fan-out:
await _hub.Clients.Group($"company:{cid}").SendAsync("cot.received", evt);
```
""",
        "relationships": "Foundation of pub/sub (observer = in-process pub/sub).  Pairs with mediator (observer is point-to-point; mediator centralizes routing).  Often composed with circuit-breaker for protecting observers from a flaky subject.",
        "references": "GoF Observer; React state model; SignalR hubs",
    },
    {
        "slug": "template-method",
        "name": "Template Method",
        "category": "classical",
        "intent": "Define the skeleton of an algorithm in a base method, deferring some steps to subclasses",
        "when_to_use": """
Multiple variants follow the same overall flow but differ in specific steps: a deployment script (clone → build → test → push → restart) where each step varies by target stack.

You want to enforce the OVERALL sequence while letting subclasses customize steps.
""",
        "when_not_to_use": """
Subclasses end up overriding most steps — use strategy instead.

The 'algorithm' is one line and the override is the whole point — just use polymorphism directly.
""",
        "structure": "Base class defines a non-virtual template method that calls protected virtual primitives.  Subclasses override the primitives but not the template.",
        "example_code": """
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
""",
        "relationships": "Compare with strategy (strategy delegates the WHOLE algorithm; template method delegates STEPS).  Foundation of frameworks (Spring transactions, ASP.NET controller lifecycle).",
        "references": "GoF Template Method",
    },

    # ============ ARCHITECTURAL ============
    {
        "slug": "clean-architecture",
        "name": "Clean Architecture",
        "category": "architectural",
        "intent": "Organize code so business rules don't depend on infrastructure, UI, or frameworks; outer layers point inward",
        "when_to_use": """
Long-lived business apps where infrastructure (DBs, queues, providers) will change but business rules persist: SaaS platforms, financial systems, regulated industries.

Multiple delivery channels (web + CLI + worker + mobile) need the same business rules.

You want testability without spinning up infra (Application tests use fake adapters).
""",
        "when_not_to_use": """
CRUD over a single DB with no business logic — a clean architecture skeleton is overhead.

Prototype / scratch code — focus on shipping; clean architecture if it survives.
""",
        "structure": """
Concentric layers, dependencies point inward:
- Domain (innermost): entities, value objects, repository INTERFACES (not implementations)
- Application: use cases, ports for infra (IEmailSender, IClock)
- Infrastructure: adapter IMPLEMENTATIONS (EF Core repos, Graph email sender)
- Api / Presentation: outermost; composition root, controllers
Domain knows nothing.  Application knows Domain.  Infrastructure knows Application + Domain.  Api knows all (it wires them).
""",
        "example_code": """
```
src/Acme.Domain/      ← entities, repository interfaces, value objects
src/Acme.Application/ ← use cases, ports, app services
src/Acme.Infrastructure/ ← EF Core, MS Graph, Service Bus adapters
src/Acme.Api/         ← controllers, composition root
```
""",
        "relationships": "Pairs with hexagonal-ports-adapters (different ways to draw the same boundary).  Pairs with repository-pattern (Domain owns the interface, Infrastructure provides it).  See also domain-driven-aggregate.",
        "references": "Uncle Bob Martin; Acme uses this — see CLAUDE.md 'Architecture boundaries'",
    },
    {
        "slug": "hexagonal-ports-adapters",
        "name": "Hexagonal (Ports & Adapters)",
        "category": "architectural",
        "intent": "Isolate the application core from external concerns via interfaces (ports) and replaceable implementations (adapters)",
        "when_to_use": """
The application has multiple input mechanisms (HTTP API, CLI, queue worker) and multiple output mechanisms (Postgres, blob storage, email, MQTT).

You want tests that swap out infra for fakes without rewriting the application.

You want the freedom to swap one provider for another (AWS S3 → Azure Blob) without rewriting business code.
""",
        "when_not_to_use": """
The 'core' is genuinely glue code over one provider — adding ports just adds indirection.

Adapters are shipped as the canonical thing (no expectation of swapping) — the port becomes a noise interface.
""",
        "structure": "Application core defines PORTS (Domain or Application interfaces: IEmailSender, IClock, IDroneRepository).  ADAPTERS implement ports against concrete tech.  Composition root wires the adapters.  Tests substitute fakes.",
        "example_code": """
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
""",
        "relationships": "Identical idea to clean-architecture, different visualization.  Foundation of dependency-injection.  Pairs with adapter pattern (every implementation IS an Adapter).  See backend-ports-and-testing.mdc in Acme.",
        "references": "Alistair Cockburn 'Hexagonal Architecture'",
    },
    {
        "slug": "repository-pattern",
        "name": "Repository",
        "category": "architectural",
        "intent": "Encapsulate data access behind a collection-like interface so domain code doesn't depend on storage tech",
        "when_to_use": """
Domain has aggregates (DDD) and you want the storage tech to be a swappable detail.

Multiple storage backends might be used (test in-memory, prod Postgres, edge SQLite).

You want queries expressed in domain terms ('drones in fleet X') not SQL.
""",
        "when_not_to_use": """
Repository becomes a thin wrapper over an ORM — you've added a layer with no benefit.  Just use the ORM.

You're hiding the ORM but every consumer drops to raw SQL anyway — accept the leak or change the design.
""",
        "structure": "Repository interface in Domain.  EF/Mongo/Dapper implementation in Infrastructure.  Methods are domain-language: AddDrone, GetByFleet, FindActiveByTenant.",
        "example_code": """
```csharp
public interface IDroneRepository {
    Task<Drone?> GetAsync(DroneId id, CancellationToken ct);
    Task<IReadOnlyList<Drone>> ListByFleetAsync(FleetId fleet, CancellationToken ct);
    Task AddAsync(Drone d, CancellationToken ct);
    Task SaveChangesAsync(CancellationToken ct);
}
```
""",
        "relationships": "Lives at the Application/Infrastructure boundary in clean-architecture.  Pairs with unit-of-work (SaveChangesAsync = UoW commit).  Foundation of aggregate-root persistence.",
        "references": "Fowler PEAA; DDD Blue Book",
    },
    {
        "slug": "cqrs",
        "name": "CQRS (Command Query Responsibility Segregation)",
        "category": "architectural",
        "intent": "Split read and write models so each can be optimized independently",
        "when_to_use": """
Reads and writes have wildly different shapes / load profiles (analytics dashboard vs transactional writes).

The write model is a strict aggregate (consistency), reads are flexible projections (eventual consistency OK).

Multiple read shapes for the same data (per-user feed, per-tenant report, full-text index) all derived from one write model.
""",
        "when_not_to_use": """
Simple CRUD where reads + writes share the same model.  CQRS triples complexity for no value.

You don't have a way to keep the read projection in sync with writes (no event log, no triggers).
""",
        "structure": "Commands mutate state via the write model (the aggregate / repository).  Queries read from denormalized projections.  An event/outbox propagates writes to projections.  Reads are typically eventually consistent.",
        "example_code": """
```csharp
// Write side
public class IssueDroneCommandHandler {
    public async Task Handle(DroneCommand cmd) {
        var drone = await _repo.GetAsync(cmd.DroneId);
        drone.Apply(cmd);
        await _repo.SaveChangesAsync();
        await _outbox.PublishAsync(new DroneCommandIssued(cmd));
    }
}

// Read side — separate denormalized projection
public class DroneCockpitQuery {
    public async Task<DroneCockpitView> Get(DroneId id) =>
        await _readDb.GetByDroneIdAsync(id);  // not the same DB; not the same shape
}
```
""",
        "relationships": "Pairs with event-sourcing (writes = events, projections = read models).  Pairs with outbox-pattern.  Foundation of read-replica / search-index architectures.",
        "references": "Greg Young CQRS Documents",
    },
    {
        "slug": "event-sourcing",
        "name": "Event Sourcing",
        "category": "architectural",
        "intent": "Store the sequence of state CHANGES, not the current state; rebuild state by replaying events",
        "when_to_use": """
Audit is the product: regulatory systems, financial ledgers, blackbox flight recorders.

You need to ask 'what was the state at time T?' as a first-class query.

Multiple projections need to be derivable from the same source of truth.
""",
        "when_not_to_use": """
The current state IS what matters and the history is uninteresting.

You can't bound the event volume (millions per second with no archival path) — event sourcing under load needs serious infra.
""",
        "structure": "Append-only event log.  Aggregates rebuild from events.  Snapshots accelerate replay.  Projections subscribe to the log and materialize views.",
        "example_code": """
```typescript
type DroneEvent =
  | { kind: 'DroneEnrolled', t: Date, droneId: string, fingerprint: string }
  | { kind: 'CommandIssued', t: Date, cmd: DroneCommand }
  | { kind: 'TelemetryReceived', t: Date, sample: TelemetrySample };

class Drone {
  static fromHistory(events: DroneEvent[]): Drone {
    const d = new Drone();
    for (const e of events) d.apply(e);
    return d;
  }
  apply(e: DroneEvent) { /* fold */ }
}
```
""",
        "relationships": "Pairs with CQRS (events drive projections).  Adjacent to outbox-pattern (events as messages).  The blackbox use case in mz-pid-tuner is event-sourcing in the small.",
        "references": "Greg Young; Vaughn Vernon 'Implementing DDD'",
    },
    {
        "slug": "service-layer",
        "name": "Service Layer",
        "category": "architectural",
        "intent": "A layer of application services that orchestrate domain logic and infrastructure for a use case",
        "when_to_use": """
Use cases involve multiple domain entities + side effects (publish event, send email, write blob).  The service layer is the orchestrator.

You want a clean boundary between presentation (controllers) and domain.

Multiple delivery channels (web, CLI, worker) call the same use case.
""",
        "when_not_to_use": """
Services become a dumping ground of unrelated methods on a god-class — split by use case.

The service has zero orchestration (just delegates to one repo call) — call the repo directly.
""",
        "structure": "AppService classes named by use case domain (DroneCommandAppService, DeviceIngestionAppService).  Methods take DTOs, return DTOs.  Inside: load aggregate → mutate → save → publish event.",
        "example_code": """
```csharp
public class DroneCommandAppService {
    public async Task<DroneCommand> IssueAsync(IssueRequest req, CancellationToken ct) {
        var drone = await _drones.GetAsync(req.DroneId, ct);
        var cmd = drone.Issue(req.Verb, req.Payload, _clock.Now);
        await _drones.SaveChangesAsync(ct);
        await _broadcaster.BroadcastAsync(cmd, ct);
        return cmd;
    }
}
```
""",
        "relationships": "Foundation of clean-architecture Application layer.  Pairs with repository-pattern.  Distinct from Domain Service (DDD) which has domain logic that doesn't fit an entity.",
        "references": "Fowler PEAA; Acme uses this pattern throughout Acme.Application",
    },
    {
        "slug": "domain-driven-aggregate",
        "name": "Aggregate (DDD)",
        "category": "architectural",
        "intent": "Cluster of domain objects treated as a single transactional unit, with one root that enforces invariants",
        "when_to_use": """
Domain has complex invariants spanning multiple entities (a Swarm + its FormationPolicy + its FleetHome must stay consistent).

You want clear transactional boundaries (the aggregate is what gets saved atomically).

Concurrent updates need predictable conflict semantics — the aggregate is the unit of optimistic locking.
""",
        "when_not_to_use": """
Anemic domain — your 'aggregates' are just DTOs with no behavior.  Aggregates are useless if entities don't enforce invariants.

You're forcing a small operation into a huge aggregate just because — split it.  Smaller aggregates are better.
""",
        "structure": "Aggregate root is the only externally-visible entity.  Internal entities and value objects are accessed only via the root.  All mutations go through the root.  Persistence is per-aggregate, atomically.",
        "example_code": """
```csharp
public class Swarm : AggregateRoot {  // root
    private readonly List<DroneId> _members = new();
    public FleetHome Home { get; private set; }  // internal entity
    public FormationPolicyId ActiveFormation { get; private set; }

    public void FormUp() {  // mutation goes through root
        EnsureCanFormUp();  // invariant
        Home.Activate();
        ActiveFormation = ...;
        AddDomainEvent(new SwarmFormedUp(Id));
    }
}
```
""",
        "relationships": "Foundation of DDD.  Pairs with repository-pattern (one repo per aggregate).  Pairs with composite (Swarm IS a Composite<Drone> conceptually).",
        "references": "Vaughn Vernon 'Implementing DDD'",
    },
    {
        "slug": "mvc-mvp-mvvm",
        "name": "MVC / MVP / MVVM",
        "category": "architectural",
        "intent": "Separate UI presentation from business logic via Model + View + Controller/Presenter/ViewModel",
        "when_to_use": """
Any non-trivial UI app: web, mobile, desktop.  Picking the variant depends on the framework:
- MVC: server-rendered HTML (ASP.NET MVC, Rails)
- MVVM: data-binding-heavy frameworks (WPF, modern XAML, Vue/Angular)
- MVP: classic Android, plain WinForms

The View is dumb (renders), the Model is the domain, the middle thing (Controller/Presenter/ViewModel) wires user input to model changes.
""",
        "when_not_to_use": """
A single-screen tool — the layering is overhead.

The 'controller' has become a god-class — split into multiple controllers/presenters by use case.

You're using React or modern reactive UIs where the model is reactive state (Redux store, signals) and 'controller' is just event handlers — the labels stop helping; embrace your framework's idioms.
""",
        "structure": "Model = data + business rules.  View = rendering.  Controller/Presenter/ViewModel = the glue: takes user input, calls Model, presents Model state to the View.",
        "example_code": """
```typescript
// Modern MVVM-ish React with TanStack Query — the 'ViewModel' is the hook
function useFleetCockpit(fleetId: FleetId) {
  const { data: fleet } = useQuery({ queryKey: ['fleet', fleetId], queryFn: () => api.getFleet(fleetId) });
  const issue = useMutation({ mutationFn: (cmd: FleetCommand) => api.issueFleetCommand(fleetId, cmd) });
  return { fleet, issue };
}
function FleetCockpitPage() {
  const { fleet, issue } = useFleetCockpit(fleetId);  // ViewModel
  return <FleetMap fleet={fleet} onFormUp={() => issue.mutate({ verb: 'form-up' })} />;
}
```
""",
        "relationships": "Foundation of UI architecture.  Pairs with reactive-state-management (Redux, MobX, signals).  Foundation under the Acme web SPA.",
        "references": "Trygve Reenskaug; Fowler PEAA",
    },

    # ============ RESILIENCE ============
    {
        "slug": "circuit-breaker",
        "name": "Circuit Breaker",
        "category": "resilience",
        "intent": "Stop calling a failing dependency for a cooldown period so the dependency can recover and callers fail fast",
        "when_to_use": """
Synchronous calls to a dependency that can degrade or fail (HTTP API, MQTT broker, database).

The cost of repeatedly attempting calls during an outage is high (latency, resource exhaustion, cascading failure).

You want fast failure during outages instead of slow timeouts.
""",
        "when_not_to_use": """
Internal calls in a single process — circuit breakers add latency tracking + state machine; not worth it.

Backends that are designed to handle infinite retries (idempotent enqueues) — just retry.

You haven't tuned the threshold + cooldown — defaults often produce more harm than good.
""",
        "structure": "States: Closed (calls flow), Open (calls fast-fail), Half-Open (a probe call decides whether to close).  Threshold = consecutive failures or failure rate.  Cooldown = how long Open lasts.",
        "example_code": """
```csharp
services.AddHttpClient<IFooClient, FooClient>()
    .AddPolicyHandler(Policy<HttpResponseMessage>
        .Handle<HttpRequestException>()
        .CircuitBreakerAsync(
            handledEventsAllowedBeforeBreaking: 5,
            durationOfBreak: TimeSpan.FromSeconds(30)));
```
""",
        "relationships": "Foundation of resilient systems.  Pairs with retry-with-exponential-backoff-jitter (retry then breaker, not breaker then retry).  Pairs with fallback (when breaker is open, fallback fires).  Pairs with bulkhead (per-dependency isolation).",
        "references": "Michael Nygard 'Release It!'; Polly docs",
    },
    {
        "slug": "retry-with-exponential-backoff-jitter",
        "name": "Retry with Exponential Backoff + Jitter",
        "category": "resilience",
        "intent": "Retry transient failures with growing delays, randomized to avoid thundering herd",
        "when_to_use": """
Transient failures (network blip, brief overload, conflict that resolves under retry).

The operation is idempotent OR you have an idempotency token.

The downstream can absorb retries (you're not making the problem worse).
""",
        "when_not_to_use": """
The operation isn't idempotent and there's no token — retrying double-charges, double-sends.

You're retrying inside a retry (compounding exponentials = surprise outage).

The failure is permanent (4xx, schema mismatch) — don't retry 4xx.

You're not jittering — synchronized retries trigger thundering herd.
""",
        "structure": "Attempt → on transient failure, wait base * 2^attempt + random(0, jitter) → retry up to max attempts.  Cap the max delay.  Distinguish transient vs permanent failures.",
        "example_code": """
```csharp
services.AddHttpClient<IFooClient, FooClient>()
    .AddPolicyHandler(Policy<HttpResponseMessage>
        .Handle<HttpRequestException>()
        .OrResult(r => (int)r.StatusCode >= 500)
        .WaitAndRetryAsync(
            retryCount: 4,
            sleepDurationProvider: i =>
                TimeSpan.FromMilliseconds(Math.Min(60_000,
                    200 * Math.Pow(2, i) + new Random().Next(0, 250)))));
```
""",
        "relationships": "Layer ORDER: retry-INSIDE circuit-breaker, not outside (breaker bounds total work).  Pairs with idempotency-token.  Pairs with timeout (each retry attempt has its own).",
        "references": "Polly; AWS Architecture Blog 'Exponential backoff and jitter'",
    },
    {
        "slug": "bulkhead",
        "name": "Bulkhead",
        "category": "resilience",
        "intent": "Isolate resource pools per dependency so a slow dependency doesn't drain everything",
        "when_to_use": """
You have multiple downstream dependencies sharing one pool (thread pool, connection pool, queue) — a slow one can starve fast ones.

You want to bound concurrent calls to a specific dependency so it can't overwhelm itself.

Background work shouldn't be able to starve interactive work.
""",
        "when_not_to_use": """
You have only one downstream and one workload class — bulkhead is unnecessary.

The 'bulkhead' isolates things that genuinely share state — you've added latency without isolation benefit.
""",
        "structure": "Per-dependency thread pool / semaphore / connection pool.  Hard cap on concurrent operations.  Excess work queues, throttles, or fast-fails.",
        "example_code": """
```csharp
services.AddHttpClient<IFooClient, FooClient>()
    .AddPolicyHandler(Policy.BulkheadAsync<HttpResponseMessage>(
        maxParallelization: 10,
        maxQueuingActions: 50,
        onBulkheadRejectedAsync: ctx => { /* log + fast fail */ }));
```
""",
        "relationships": "Pairs with circuit-breaker (per-dependency isolation).  Pairs with rate-limiter (bound rate; bulkhead bounds concurrency).  Foundation of the Acme companion offline-queue pattern.",
        "references": "Michael Nygard 'Release It!'; Polly Bulkhead",
    },
    {
        "slug": "timeout-and-deadline",
        "name": "Timeout + Deadline",
        "category": "resilience",
        "intent": "Bound how long any individual call can take; cancel and free resources if exceeded",
        "when_to_use": """
EVERY synchronous external call — without exception.  No timeout = guaranteed eventual hang.

Long-running operations that should give up if upstream changes (user navigated away, request cancelled).

End-to-end deadlines: the caller has 30s total budget; pass that down so each step knows how much remains.
""",
        "when_not_to_use": """
Timeout shorter than the operation's natural latency — guaranteed false-positive failures.

Timeout without a circuit breaker — you fail fast on each call but keep slamming the downstream.

Cancellation tokens that no one observes — paper timeout, real hang.
""",
        "structure": "Total time budget for an operation.  Propagated via CancellationToken / context.WithDeadline.  Each layer reads its remaining budget and shortens its own.",
        "example_code": """
```csharp
using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(30));
await client.SendAsync(request, cts.Token);
// Combined with Polly timeout policy for redundancy:
.AddPolicyHandler(Policy.TimeoutAsync<HttpResponseMessage>(15));
```
""",
        "relationships": "Pairs with circuit-breaker (timeout failures feed the breaker's count).  Pairs with retry (each attempt has its own timeout; retry budget < deadline).  Pairs with bulkhead (timeouts free pooled resources back).",
        "references": "Polly Timeout; gRPC deadlines",
    },
    {
        "slug": "fallback",
        "name": "Fallback",
        "category": "resilience",
        "intent": "Substitute a degraded-but-useful response when the primary path fails",
        "when_to_use": """
A degraded answer is still useful: cached value, default, last-known-good, simplified UI.

The primary fails for a reason the fallback isn't subject to (independent failure modes).

The user experience is graceful degradation, not error.
""",
        "when_not_to_use": """
There's no honest fallback — returning empty / null / stale is worse than failing visibly.

The fallback masks a real bug — alerting + visible failure surface the issue faster.

The fallback diverges from the primary in a way that creates split-brain.
""",
        "structure": "Primary call → on failure → fallback path.  Fallback is documented as 'degraded mode' so it's never mistaken for normal.",
        "example_code": """
```csharp
services.AddHttpClient<IWeatherClient, WeatherClient>()
    .AddPolicyHandler(Policy<HttpResponseMessage>
        .Handle<Exception>()
        .FallbackAsync(
            fallbackAction: ct => Task.FromResult(_lastKnownGood.Value),
            onFallbackAsync: ex => _metrics.Increment("weather.fallback.fired")));
```
""",
        "relationships": "Pairs with circuit-breaker (when breaker is open, fallback fires).  Pairs with graceful-degradation (system-level fallback).",
        "references": "Polly Fallback; 'Release It!'",
    },
    {
        "slug": "health-check-readiness-liveness",
        "name": "Health Check / Readiness / Liveness",
        "category": "resilience",
        "intent": "Distinct probes signaling whether the process is alive vs ready to serve traffic vs which dependencies are degraded",
        "when_to_use": """
Containerized / orchestrated environments where the platform decides when to restart / route traffic.

Multi-dependency apps where you need to distinguish 'I crashed' from 'broker is down but ingest still works'.

Operations needs a fast probe for monitoring + a deep probe for diagnostics.
""",
        "when_not_to_use": """
Single static binary on a single host with no orchestration — overhead.

Probes that hit downstream services synchronously without timeout — the probe becomes a DoS vector.
""",
        "structure": """
Liveness (/health/live): is the process running and serving HTTP at all?  Restart if not.
Readiness (/health/ready): all hard dependencies up?  Route traffic if so.  Returns 'degraded' (200) when soft deps are down but service still useful.
Details (/health/details): full diagnostic — per-dep timings, last error, breaker state.  Auth-gated.
""",
        "example_code": """
```csharp
services.AddHealthChecks()
    .AddNpgSql(_pg, tags: new[] { "ready" })
    .AddRabbitMQ(_amqp, tags: new[] { "ready", "degradable" })
    .AddCheck<MqttBrokerCheck>("mqtt", tags: new[] { "degradable" });

app.MapHealthChecks("/health/live", new HealthCheckOptions { Predicate = _ => false });
app.MapHealthChecks("/health/ready", new HealthCheckOptions { Predicate = c => c.Tags.Contains("ready") });
```
""",
        "relationships": "Pairs with circuit-breaker (breaker state surfaces in /details).  Foundation of platform-driven self-healing.  Acme uses this — see CLAUDE.md Health endpoints table.",
        "references": "Kubernetes probes; ASP.NET HealthChecks",
    },
    {
        "slug": "idempotency-token",
        "name": "Idempotency Token",
        "category": "resilience",
        "intent": "Make a non-idempotent operation safely retryable by deduplicating on a client-supplied unique token",
        "when_to_use": """
Operations with side effects you cannot undo: payment authorization, message dispatch, drone command issuance.

You want to allow retries (network blip, timeout) without double-actions.

Network is unreliable enough that the client genuinely doesn't know if its first attempt succeeded.
""",
        "when_not_to_use": """
The operation is already idempotent by nature (PUT, conditional update).

You're not actually deduplicating — the token is decorative.  Real dedup needs a unique-key constraint + 'already exists' handling.
""",
        "structure": "Client generates a UUID per logical operation.  Server stores (token → result) in a dedup cache.  Repeated POST with same token returns the cached result (not a re-execution).  TTL bounds the cache.",
        "example_code": """
```csharp
public async Task<CommandResult> Issue(IssueRequest req, string idempotencyKey) {
    var cached = await _dedup.GetAsync(idempotencyKey);
    if (cached != null) return cached;

    var result = await DoIssue(req);
    await _dedup.SetAsync(idempotencyKey, result, ttl: TimeSpan.FromHours(24));
    return result;
}
```
""",
        "relationships": "Foundation of safe retry.  Pairs with retry-with-exponential-backoff-jitter.  Pairs with outbox-pattern (outbox row IS an idempotency token for downstream delivery).",
        "references": "Stripe's idempotency-key header docs; RFC draft-ietf-httpapi-idempotency-key-header",
    },
    {
        "slug": "queue-based-load-leveling",
        "name": "Queue-Based Load Leveling",
        "category": "resilience",
        "intent": "Decouple producers from consumers via a queue so spikes don't overwhelm downstream",
        "when_to_use": """
Producer burst rate >> consumer steady rate (a thousand telemetry samples land in 1 second; the analyzer processes 100/s).

Producer and consumer have different scaling characteristics.

Failures on the consumer side shouldn't block producers (the queue absorbs).
""",
        "when_not_to_use": """
The operation is genuinely synchronous (the producer needs the result to continue).  Don't queue what you need now.

The queue grows unboundedly and you've not addressed the underlying mismatch — added latency, not solved a problem.
""",
        "structure": "Producer enqueues fire-and-forget.  Queue (RabbitMQ, ServiceBus, SQS, in-proc Channel) buffers.  Consumer dequeues at its own pace, with retry on failure (often dead-letter on max retries).",
        "example_code": """
```csharp
// Producer
await _channel.Writer.WriteAsync(new TelemetrySample(...));

// Consumer (background service)
await foreach (var sample in _channel.Reader.ReadAllAsync(ct)) {
    await _processor.HandleAsync(sample, ct);
}
```
""",
        "relationships": "Pairs with bulkhead (one consumer pool per queue).  Foundation of background-processing / worker patterns.  Pairs with outbox-pattern for guaranteed delivery.",
        "references": "Microsoft Azure 'Queue-Based Load Leveling pattern'",
    },

    # ============ OFFLINE-FIRST ============
    {
        "slug": "local-first-architecture",
        "name": "Local-First Architecture",
        "category": "offline",
        "intent": "Data lives primarily on the user's device; sync to cloud is optional and best-effort",
        "when_to_use": """
Users work disconnected (field tech, drone pilots in flight, traveling sales, anyone with flaky connectivity).

Latency-sensitive UI (typing in a doc, drawing on a map) — round-trips to a server feel laggy.

Multi-device per user where each device should keep working independently.
""",
        "when_not_to_use": """
Data is fundamentally shared real-time across users (a multiplayer game state).

Data is so large it can't fit on the device (cloud-native is the only option).

Strict server-side authorization is the source of truth (banking transactions).
""",
        "structure": "Local DB on device is the source of truth FOR THE USER.  Sync engine bidirectionally reconciles with a cloud DB when connectivity is available.  Conflicts are resolved deterministically (CRDT, LWW, vector clocks).",
        "example_code": """
The Acme companion app: telemetry queued locally via offline-queue, drained to /devices/ingest when connected.  Drone firmware: device commands cached on SD card, pulled back to server when connected.  See arch-fc-param-pipeline memory entry.
""",
        "relationships": "Pairs with crdt (the merge math).  Pairs with outbox-pattern (queued mutations).  Pairs with sync-engine (bidirectional reconciliation).  Foundation of Acme offline-survivable pipeline.",
        "references": "Ink & Switch 'Local-first software'; Martin Kleppmann",
    },
    {
        "slug": "outbox-pattern",
        "name": "Outbox Pattern",
        "category": "offline",
        "intent": "Write business state + outbound messages in one local transaction; a separate process drains messages to the wire",
        "when_to_use": """
Need to atomically update a DB AND publish an event/message.  The 'and' is the hard part (two-phase commit is fragile; dual writes are broken).

You want at-least-once delivery without losing messages on crash.

Offline-first systems: messages queue locally and flush when connectivity returns.
""",
        "when_not_to_use": """
Fire-and-forget that doesn't matter if lost (analytics ping).

You can use a transactional log feature directly (PostgreSQL logical replication, change-data-capture) — that's the outbox built-in.
""",
        "structure": "Application writes business state + an Outbox row in the same DB transaction.  A separate poller / CDC subscriber reads Outbox, publishes to the wire, marks rows as sent.  At-least-once: subscribers must be idempotent.",
        "example_code": """
```sql
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE id = $1;
INSERT INTO outbox (kind, payload) VALUES ('AccountDebited', $2);
COMMIT;
```
A background worker selects unsent outbox rows, publishes, marks sent.
""",
        "relationships": "Foundation of reliable event publication.  Pairs with idempotency-token (downstream dedup).  Pairs with eventually-consistent-replication.  Used in Acme CoT bridge between API and TAK fan-out.",
        "references": "Microservices Patterns by Chris Richardson",
    },
    {
        "slug": "crdt",
        "name": "CRDT (Conflict-free Replicated Data Type)",
        "category": "offline",
        "intent": "Data types where concurrent edits merge deterministically without coordination",
        "when_to_use": """
Multi-device editing of the same data with possibly-disconnected periods.

Distributed counters / sets that need to converge after partition heals (Acme swarm state).

You want NO server-side merge logic — the math guarantees convergence regardless of message order.
""",
        "when_not_to_use": """
Operations are intrinsically serial (a bank ledger — order matters for correctness).

The data has invariants CRDTs can't express (a unique constraint across the dataset).

You haven't picked the right CRDT — picking 'just an LWW register' for something complex causes silent data loss.
""",
        "structure": "Operations are commutative + associative + idempotent (or use vector clocks).  Common CRDTs: G-Counter, PN-Counter, LWW-Register, OR-Set, RGA (sequence).  Sync exchanges deltas or full state.",
        "example_code": """
```cpp
// Swarm peer-state in mz-pid-tuner uses LWW-Register per peer:
struct PeerEntry {
    PeerIdentity id;
    uint64_t lamport_stamp;
    PeerState state;
};
// Merge: pick higher lamport_stamp; ties broken by peer id.
```
""",
        "relationships": "Foundation of local-first-architecture sync engines.  Pairs with vector-clocks-lww.  Alternative to operational-transform.  Used in mz-pid-tuner swarm_state.",
        "references": "Shapiro et al. 'Conflict-free Replicated Data Types'; Automerge; Yjs",
    },
    {
        "slug": "offline-queue-bulkhead",
        "name": "Offline Queue (Bulkhead between Online + Offline)",
        "category": "offline",
        "intent": "Persistent local queue that decouples production from delivery so producers never block on the network",
        "when_to_use": """
Devices that periodically lose connectivity (companion app on a phone, drone with cellular dropouts).

Multiple producers feeding multiple delivery channels: telemetry → device-ingest, CoT → TAK fan-out, blackbox → upload.  One queue per channel = independent retry budgets.

You need at-least-once delivery across crashes (the queue is on disk).
""",
        "when_not_to_use": """
Volatile data that's worthless if delivered late — don't queue it; drop on disconnect.

The queue size could grow unbounded — set a retention policy or risk filling the disk.
""",
        "structure": "Each event class has its own queue (independent backpressure).  Persistent (sqlite, plain file, embedded LMDB).  Drainer task per queue: reads next, sends, marks sent on ack, retries on failure.",
        "example_code": """
The Acme companion's packages/offline-queue is exactly this.  Three streams: pilot telemetry, CoT events, swarm-state — each independently queued + drained.  See arch-fc-param-pipeline.
""",
        "relationships": "Pairs with outbox-pattern (queue persisted in a transactional DB).  Pairs with bulkhead (per-stream isolation).  Foundation of local-first-architecture.",
        "references": "Acme apps/companion packages/offline-queue",
    },
    {
        "slug": "optimistic-ui",
        "name": "Optimistic UI",
        "category": "offline",
        "intent": "Apply the user's change locally immediately; reconcile with the server result later",
        "when_to_use": """
The user is doing a confident action (typing, dragging, clicking a confirmed button) and they expect immediate feedback.

The change usually succeeds; server-side rejection is rare.

You can roll back gracefully on rejection (no destructive side effects already triggered).
""",
        "when_not_to_use": """
The action has irreversible side effects from the user's perspective (sending money, sending a message visible to others).

The conflict rate is high — users see flickering reverts.
""",
        "structure": "Mutation fires; UI updates immediately.  Server call happens in the background.  On server success: confirm.  On server failure: roll back + surface the error.  Often paired with TanStack Query's onMutate.",
        "example_code": """
```typescript
const issue = useMutation({
  mutationFn: (cmd: DroneCommand) => api.issue(droneId, cmd),
  onMutate: async (cmd) => {
    await queryClient.cancelQueries(['drone', droneId]);
    const prev = queryClient.getQueryData(['drone', droneId]);
    queryClient.setQueryData(['drone', droneId], applyOptimistically(prev, cmd));
    return { prev };
  },
  onError: (err, cmd, ctx) => queryClient.setQueryData(['drone', droneId], ctx?.prev),
  onSettled: () => queryClient.invalidateQueries(['drone', droneId]),
});
```
""",
        "relationships": "Pairs with local-first-architecture (offline = always optimistic).  Pairs with retry / outbox (if the call fails for transient reasons).",
        "references": "TanStack Query docs; React Query patterns",
    },
    {
        "slug": "eventually-consistent-replication",
        "name": "Eventually Consistent Replication",
        "category": "offline",
        "intent": "Accept that replicas may diverge transiently; guarantee convergence given pause in writes",
        "when_to_use": """
Multi-region / multi-device systems where strong consistency is too expensive or impossible.

Read-heavy workloads where reading stale-by-seconds is fine.

Offline + sync architectures where partitions are normal, not exceptional.
""",
        "when_not_to_use": """
Operations require strong consistency (bank balances, inventory counts under contention).

Users would be confused or harmed by seeing stale state.
""",
        "structure": "Writes accepted at any replica.  Replicas exchange changes asynchronously.  Conflicts resolved by CRDT / LWW / vector clocks.  System provides 'monotonic reads' and 'read-your-writes' guarantees where possible.",
        "example_code": "swarm state in mz-pid-tuner; the Acme fleet view eventually consistent with edge devices.",
        "relationships": "Pairs with crdt.  Pairs with local-first-architecture.  Foundation of distributed-systems.",
        "references": "Werner Vogels 'Eventually Consistent'; DDIA",
    },

    # ============ AI ============
    {
        "slug": "rag-retrieval-augmented-generation",
        "name": "RAG (Retrieval-Augmented Generation)",
        "category": "ai",
        "intent": "Ground LLM responses in retrieved documents so answers reflect a specific corpus, not just training data",
        "when_to_use": """
You need the LLM to answer from YOUR data (codebase, knowledge base, ticket history) — not its training data.

The corpus updates frequently and you can't fine-tune fast enough.

Auditability matters: citations to source documents are required.

The rote catalogs (scripts, anti-patterns, design-patterns, technologies) themselves ARE RAG — semantic search via embeddings, the LLM gets the matched documents in context.
""",
        "when_not_to_use": """
The model already knows enough — RAG adds latency without value.

The retrieval index is stale relative to truth — confidently-cited wrong answers.

The corpus is small enough to put in the system prompt — no index needed.
""",
        "structure": "Index: embed documents, store in vector DB.  Retrieve: embed query, find top-k similar.  Augment: stuff retrieved chunks into the LLM prompt.  Generate: LLM answers conditioned on the chunks.",
        "example_code": """
```python
# Rote is RAG over your own scripts + anti-patterns:
def find(query: str):
    vec = embed(query)
    chunks = sqlite_vec.search("scripts_vec", vec, k=5)
    return chunks  # LLM uses these in its next response
```
""",
        "relationships": "Foundation of LLM apps over private data.  Pairs with semantic-search-with-embeddings.  Pairs with structured-output-with-schema (force the answer to cite sources).  Variants: self-rag (model decides what to retrieve), GraphRAG (retrieval over a knowledge graph).",
        "references": "Lewis et al. 'Retrieval-Augmented Generation'; Anthropic Contextual Retrieval",
    },
    {
        "slug": "react-reasoning-and-acting",
        "name": "ReAct (Reasoning + Acting)",
        "category": "ai",
        "intent": "Interleave reasoning steps with tool-use actions so the LLM can investigate before answering",
        "when_to_use": """
The user's question requires multi-step lookups / actions where the next step depends on prior results.

Tools are available (search, calculator, code execution, MCP servers).

You want the model's reasoning visible / auditable.

Classic shape: 'Thought → Action → Observation → Thought → ... → Final Answer.'
""",
        "when_not_to_use": """
A single tool call suffices — the reasoning loop is overhead.

Tools are expensive and the model misuses them — guardrail the loop with budgets.

Latency is critical — multiple LLM turns + tool calls compound.
""",
        "structure": "System prompt enables tools.  Each turn: LLM either (a) thinks aloud, (b) calls a tool, or (c) finalizes.  Run until 'final answer' or budget exhausted.  Modern frameworks: OpenAI function calling, Anthropic tool use, MCP.",
        "example_code": """
Claude Code agent loop IS ReAct.  Each turn: Claude thinks, then either calls a tool (Read, Bash, Skill) or answers.
""",
        "relationships": "Foundation of agentic LLM apps.  Pairs with tool-use-function-calling (the mechanism).  Pairs with rag-retrieval-augmented-generation (retrieval is a tool).  Pairs with structured-output-with-schema (force structured tool args).",
        "references": "Yao et al. 'ReAct: Synergizing Reasoning and Acting'",
    },
    {
        "slug": "tool-use-function-calling",
        "name": "Tool Use / Function Calling",
        "category": "ai",
        "intent": "Let the LLM trigger external actions by emitting structured tool-call requests that the runtime executes",
        "when_to_use": """
The LLM needs to act on the world (read a file, query a DB, run a script, call an API).

The user expects the model to operate on the runtime, not just answer in text.

You want predictable, structured arguments instead of regex-parsing a free-text answer.
""",
        "when_not_to_use": """
The model can answer in text without acting — don't reach for tools.

The tool surface is huge and the model picks the wrong tool — narrow the surface or use an aggregator (MetaMCP).

Tools have irreversible side effects and you don't have user confirmation — gate destructive tools.
""",
        "structure": "Tools declared with schemas (name, description, input shape).  LLM emits a tool_call block.  Runtime validates args, executes, returns the result as a tool_result.  Loop until the model produces a regular response.",
        "example_code": """
```python
tools = [{
  "name": "find_script",
  "description": "Semantic-search reusable scripts",
  "input_schema": {
    "type": "object",
    "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
    "required": ["query"]
  }
}]
```
""",
        "relationships": "Foundation of ReAct.  Pairs with structured-output-with-schema (schema = the tool's input contract).  Pairs with mcp-aggregator-proxy (MCP = a tool-use protocol).",
        "references": "OpenAI Function Calling; Anthropic Tool Use; MCP spec",
    },
    {
        "slug": "structured-output-with-schema",
        "name": "Structured Output with Schema",
        "category": "ai",
        "intent": "Constrain the LLM to produce JSON matching a schema so the output is parseable + validated",
        "when_to_use": """
Downstream code expects a specific JSON shape (parsing extraction results, command verbs, ontology fills).

Free-text answers are fragile and break parsers under prompt drift.

Multiple LLM calls feed each other and a shared schema keeps the contract stable.
""",
        "when_not_to_use": """
The answer is genuinely free-form prose (a summary, an explanation).

The schema is so restrictive it kills useful answers — relax it.

The model doesn't support the constraint mechanism well (older models, no JSON-mode, no schema-grammar) — use prompt-engineering + post-validation.
""",
        "structure": "Pass schema to the model (response_format json_schema, function-call return type, grammar-constrained decoding).  Validate output before using it.  Retry with feedback on schema failure.",
        "example_code": """
```python
# sglang server supports JSON-schema-guided decoding:
response = client.chat.completions.create(
  model="Qwen/Qwen2.5-7B-Instruct",
  messages=[...],
  response_format={
    "type": "json_schema",
    "json_schema": {"name": "incident", "schema": INCIDENT_SCHEMA, "strict": True}
  }
)
```
""",
        "relationships": "Foundation of reliable LLM-in-pipeline.  Pairs with tool-use-function-calling.  Used by the rote dispatch-to-sglang.sh script's --schema flag.",
        "references": "OpenAI Structured Outputs; Outlines library; sglang RadixAttention",
    },
    {
        "slug": "semantic-search-with-embeddings",
        "name": "Semantic Search with Embeddings",
        "category": "ai",
        "intent": "Find documents by meaning, not keywords, by comparing embedding vectors",
        "when_to_use": """
Users phrase queries differently from how documents are indexed.

You want 'similar to X' as a query type, not just exact match.

You're building a RAG retrieval step.
""",
        "when_not_to_use": """
Exact keyword match is what the user means — full-text search is faster + cheaper.

The corpus is so small embeddings are overkill.

You can't keep the index in sync with the corpus — semantic search returns plausibly-wrong results.
""",
        "structure": "Embed each document → store vector + metadata.  Embed query → cosine distance → top-k.  Optional: rerank with a cross-encoder for better precision on the top results.",
        "example_code": """
```python
# The rote uses sqlite-vec for this:
def search(query: str, k: int = 5):
    qvec = embed(query)
    return db.execute(
        "SELECT slug, distance FROM scripts_vec WHERE embedding MATCH ? AND k = ?",
        (qvec, k)
    ).fetchall()
```
""",
        "relationships": "Foundation of RAG.  Pairs with hybrid-search (combine with BM25 keyword for best results).  Used throughout the rote (scripts, anti-patterns, design-patterns, technologies).",
        "references": "sqlite-vec; FAISS; Chroma; pgvector",
    },
    {
        "slug": "mcp-aggregator-proxy",
        "name": "MCP Aggregator / Proxy",
        "category": "ai",
        "intent": "Expose multiple downstream MCP servers as a single endpoint so clients see one unified tool surface",
        "when_to_use": """
Multiple MCP servers (rote, codebase tools, deployment tools) but LLM clients want one connection.

You want central auth / rate-limit / audit across many tool surfaces.

Tools live on different hosts; a proxy reaches them on the LLM's behalf.

Example: MetaMCP on edge-host aggregates this library's MCP server + others.
""",
        "when_not_to_use": """
One MCP server is enough — direct connection.

The aggregator becomes a single point of failure with no high-availability story.

The latency cost of the proxy hop swamps the convenience.
""",
        "structure": "Aggregator presents a unified tools/list (union of downstream tools).  Each tool call is routed to the right downstream server.  Auth + session state managed at the aggregator boundary.",
        "example_code": """
MetaMCP at http://edge-host:12008/metamcp/{endpoint}/mcp with Bearer auth proxies to N downstream MCP servers per endpoint namespace.  Any LLM connecting through MetaMCP inherits ALL of the aggregated tools.  See references/metamcp-registration.md.
""",
        "relationships": "Variant of facade-pattern / adapter for the MCP world.  Pairs with tool-use-function-calling (MCP is the protocol).  Foundation of the 'any LLM uses the same tools' story.",
        "references": "MCP spec; MetaMCP",
    },
    {
        "slug": "skill-based-prompting",
        "name": "Skill-Based Prompting",
        "category": "ai",
        "intent": "Modular, named instructions the LLM can opt into per task instead of one giant system prompt",
        "when_to_use": """
Different task types need different rules / personas / tool sets.

System prompts are getting too long to maintain or fit in context.

You want behavior to be discoverable (`/skill-name` slash commands).

Examples: Claude Code skills (chronicle, rote, secret-handling, design-patterns), task-specific prompt templates.
""",
        "when_not_to_use": """
There's only one task class — over-modularization adds discovery cost.

Skills become invisible to the model (it never reaches for them) — they're not useful at the bottom of a long prompt.

Skills overlap so much they confuse the model on selection.
""",
        "structure": "Skill file = name + when-to-invoke description + rules + cross-references.  LLM client surfaces skills as discoverable commands.  Selection is either user-triggered (slash command) or model-decided (description matches task).",
        "example_code": """
```markdown
---
name: design-patterns
description: ALWAYS invoke before designing a new class hierarchy, service layer, resilience layer, or AI-augmented feature. Returns proven patterns from the catalog so the LLM doesn't reinvent from training data.
---

(skill body)
```
""",
        "relationships": "Pairs with rag-retrieval-augmented-generation (skill content can include retrieved chunks).  Pairs with tool-use-function-calling (skills often imply tool sets).  Used throughout this library.",
        "references": "Anthropic Claude Code skills docs",
    },
    {
        "slug": "prompt-caching",
        "name": "Prompt Caching",
        "category": "ai",
        "intent": "Cache stable prompt prefixes so repeated calls pay near-zero token cost for them",
        "when_to_use": """
Long, repeated system prompts (skill stacks, large RAG context, persona descriptions).

Multi-turn conversations where the early turns don't change.

Token cost matters: caching cuts repeated tokens from ~$X/1M to ~$X/10M for cached portions.

Anthropic's prompt cache has a 5-minute TTL; calls within 5 min of each other reuse the cache.
""",
        "when_not_to_use": """
Prompts change every call — nothing to cache.

You can't structure the prompt to put stable parts first.

The marginal cost saved isn't worth the engineering — for low-volume apps.
""",
        "structure": "Put stable content FIRST in the prompt: system instructions → tool definitions → skill bodies → retrieved RAG chunks → conversation history → current user message.  Mark cache breakpoints (Anthropic) or rely on automatic prefix matching (OpenAI).",
        "example_code": """
```python
client.messages.create(
    model="claude-opus-4-8",
    system=[
        {"type": "text", "text": LARGE_SYSTEM_PROMPT},
        {"type": "text", "text": SKILL_BODIES, "cache_control": {"type": "ephemeral"}},
    ],
    messages=[...]
)
```
""",
        "relationships": "Foundational for cost-efficient LLM apps.  Pairs with skill-based-prompting (skill bodies are stable → cacheable).  Pairs with rag-retrieval-augmented-generation (retrieved chunks may or may not be cacheable depending on volatility).",
        "references": "Anthropic Prompt Caching docs; OpenAI prompt caching",
    },
    {
        "slug": "multi-agent-orchestration",
        "name": "Multi-Agent Orchestration",
        "category": "ai",
        "intent": "Decompose a task across multiple specialized LLM agents that work concurrently or in pipeline",
        "when_to_use": """
The task naturally decomposes: research → write → review.  Each step has different skills / prompts.

Independent work-items can run in parallel (review 5 files concurrently, each by a separate agent).

Context budgets are tight — splitting protects the main agent's context window.

Adversarial verification: one agent generates, another verifies independently.
""",
        "when_not_to_use": """
The task is genuinely sequential and small — multi-agent is overhead.

Coordination cost exceeds the benefit — every additional agent is a context window + LLM call.

You're using agents for things one agent does better — many tasks benefit from one coherent mind.
""",
        "structure": "Orchestrator agent (the main loop) spawns specialist agents.  Specialists work in parallel.  Results are aggregated.  Optional adversarial: one writes, another critiques.  Tools: Anthropic subagents, LangGraph, CrewAI, custom workflows.",
        "example_code": """
Claude Code's Workflow tool is multi-agent orchestration: fan-out specialists, aggregate, verify, synthesize.
""",
        "relationships": "Pairs with ReAct (each agent runs its own loop).  Pairs with skill-based-prompting (specialists have skill stacks).  Adversarial-verify pattern is multi-agent at its core.",
        "references": "Anthropic 'Building effective agents'; CrewAI; LangGraph",
    },
]


# ---------------------------------------------------------------------------
# TECHNOLOGIES
# ---------------------------------------------------------------------------
TECHNOLOGIES: list[dict] = [
    # Messaging / pub-sub
    {
        "slug": "rabbitmq",
        "name": "RabbitMQ",
        "category": "messaging",
        "implements_patterns": "queue-based-load-leveling, outbox-pattern, observer",
        "tags": "self-hosted, offline-capable, open-source, amqp, mqtt-bridge",
        "when_to_use": """
You need a self-hostable durable message broker that can run on edge / on-prem / in your own cloud.

You want flexible routing (topics, fanout, direct exchanges, headers).

You need MQTT (for IoT devices) AND AMQP (for cloud apps) on the same broker — RabbitMQ does both.

Acme uses RabbitMQ for cot-bridge ↔ broker ↔ API and as the MQTT broker for DeviceA cellular bridges.
""",
        "when_not_to_use": """
You need ordering across all messages (Kafka is built for that, RabbitMQ isn't).

Throughput requirements >100k msg/s sustained — RabbitMQ tops out; Kafka or Pulsar scale higher.

You don't want to operate it — managed alternatives exist but the offline-capable story disappears.
""",
        "limitations": """
- Routing logic complexity grows fast — keep it documented.
- Single-broker mode is a SPOF; clustering exists but adds operational weight.
- AMQP 0-9-1 is the common protocol; AMQP 1.0 support is partial.
""",
        "cost_notes": "Free open-source.  Hardware: a small broker handles 10k msg/s on commodity hardware.  Operational cost: real but manageable.",
        "alternatives": "Apache Kafka (higher throughput, ordered streams; harder to operate).  NATS (lighter, simpler).  Azure Service Bus / AWS SQS (managed, but NOT offline-capable).  Mosquitto (MQTT-only).",
        "references": "https://www.rabbitmq.com/",
    },
    {
        "slug": "mosquitto",
        "name": "Eclipse Mosquitto",
        "category": "messaging",
        "implements_patterns": "observer, queue-based-load-leveling",
        "tags": "self-hosted, offline-capable, open-source, mqtt, lightweight",
        "when_to_use": """
You need a lightweight MQTT broker for IoT devices.

You want a tiny operational footprint — Mosquitto runs on a Raspberry Pi.

You don't need AMQP / Kafka semantics — MQTT pub/sub is enough.

Acme uses Mosquitto colocated at deploy/mosquitto.conf for the public MQTT surface (mqtt.<domain>:8883).
""",
        "when_not_to_use": """
You need durable per-subscriber queues (MQTT5 helps but Mosquitto's persistence is simpler than RabbitMQ's).

You need cross-protocol bridging — RabbitMQ MQTT plugin is more flexible.

You need clustering with strong consistency — Mosquitto is single-instance by default.
""",
        "limitations": """
- Single-process; no HA built-in (use replication carefully).
- Persistence is a flat file — not designed for huge backlogs.
- Security model is per-username/password + ACL; works but feels dated next to OAuth/mTLS-native brokers.
""",
        "cost_notes": "Free open-source.  Negligible compute.",
        "alternatives": "RabbitMQ MQTT plugin (full AMQP+MQTT broker).  EMQX (commercial, higher scale).  HiveMQ (commercial).  AWS IoT Core (managed, NOT offline-capable for the broker itself).",
        "references": "https://mosquitto.org/",
    },
    {
        "slug": "azure-service-bus",
        "name": "Azure Service Bus",
        "category": "messaging",
        "implements_patterns": "queue-based-load-leveling, outbox-pattern",
        "tags": "cloud-only, managed, vendor-locked, no-offline",
        "when_to_use": """
Pure-cloud Azure-native apps that have NO offline requirement.

You want managed: no broker ops, AAD-integrated auth, SLAs.

Standard cross-region replication is nice to have.
""",
        "when_not_to_use": """
**Offline / edge / on-prem deployment** — Service Bus is cloud-only.  Acme explicitly DOES NOT USE Service Bus because devices, drones, and the GCS bundle must work disconnected.

Multi-cloud or vendor-lock-averse architectures.

Tight cost control — Service Bus charges per operation; at scale it's expensive.
""",
        "limitations": """
- Cannot run on-prem or in offline scenarios — that's the binding limitation for Acme.
- Vendor lock — Service Bus topics + subscriptions aren't trivially portable to other brokers.
- Per-message + per-connection charges; large fan-out gets expensive.
""",
        "cost_notes": "Standard tier: ~$10/mo for low volume, but scales fast.  Premium tier: $677+/month per messaging unit — for HA + dedicated resources.",
        "alternatives": "RabbitMQ self-hosted (works offline; lower ongoing cost; you operate it).  AWS SQS/SNS (same cloud-only limitation).  NATS (self-hosted, simpler than RabbitMQ).",
        "references": "https://learn.microsoft.com/azure/service-bus-messaging/",
    },
    # Realtime
    {
        "slug": "signalr",
        "name": "SignalR",
        "category": "realtime",
        "implements_patterns": "observer, rpc-over-websocket",
        "tags": "self-hosted-or-managed, .net-native, offline-capable-with-fallback, open-source",
        "when_to_use": """
.NET backend pushing realtime updates to web/mobile clients (decode progress, analysis updates, CoT activity).

You want automatic transport fallback (WebSocket → SSE → long polling) — SignalR handles it.

You want automatic reconnect, group broadcast, per-user targeting.

Acme uses SignalR for /hubs/notifications, /hubs/company-chat, /hubs/tak-activity.
""",
        "when_not_to_use": """
Non-.NET backend — Socket.IO or raw WebSockets are more portable.

You don't want clients tightly coupled to a .NET hub class shape.

You need horizontal scale-out across many backends — SignalR works with Redis/Service Bus backplane, but configure carefully.
""",
        "limitations": """
- Best with .NET clients; JS clients work well but Java/Python/Go are second-class.
- Scale-out requires a backplane (Redis, Service Bus, or Azure SignalR Service) — adds operational complexity.
- Auto-fallback transports have different feature sets; long polling is feature-poor.
""",
        "cost_notes": "Open-source server; runs alongside your API.  Azure SignalR Service: ~$1/day per 1k concurrent connections — convenient but cloud-only.",
        "alternatives": "Socket.IO (Node-native; cross-language clients good).  Raw WebSockets + your own protocol (max control).  Phoenix Channels (Elixir-native, very high scale).  Server-Sent Events (one-way only; simpler).",
        "references": "https://learn.microsoft.com/aspnet/core/signalr/",
    },
    {
        "slug": "socket-io",
        "name": "Socket.IO",
        "category": "realtime",
        "implements_patterns": "observer, rpc-over-websocket",
        "tags": "self-hosted, node-native, offline-capable-with-fallback, open-source",
        "when_to_use": """
Node.js backend with realtime needs — Socket.IO is the de facto standard.

You want WebSocket + automatic fallback (long polling) for compatibility with old proxies / corporate networks.

You want room-based broadcast, ack callbacks, namespace isolation.
""",
        "when_not_to_use": """
You're on .NET — SignalR is the local equivalent.

You can stick to raw WebSockets — less framework lock-in.

Browser-only — and the long-polling fallback isn't needed — it's overhead.
""",
        "limitations": """
- Socket.IO protocol is NOT just WebSockets — clients and servers must speak Socket.IO specifically.
- Scale-out requires a Redis adapter (or similar).
- v3/v4 protocol changes have caused upgrade pain.
""",
        "cost_notes": "Free open-source.  Server compute per concurrent connection is modest.",
        "alternatives": "Raw WebSockets (`ws`, `uWebSockets.js`).  SignalR (if you can move to .NET).  Phoenix Channels.  WebSocket Subprotocols (binary + wsSerial pattern Betaflight uses).",
        "references": "https://socket.io/",
    },
    {
        "slug": "webrtc",
        "name": "WebRTC",
        "category": "realtime",
        "implements_patterns": "peer-to-peer, low-latency-media",
        "tags": "browser-native, p2p, low-latency, complex",
        "when_to_use": """
Sub-second media latency (drone live video, voice/video calls, screen share).

Peer-to-peer with optional TURN relay — the data flows direct between peers when possible.

You're publishing to WHIP/WHEP-compatible servers (MediaMTX in Acme).
""",
        "when_not_to_use": """
File transfer / async data — use HTTP.

You need centralized recording / transcoding without a media server in the path — WebRTC alone is peer-to-peer.

You can't afford STUN/TURN infra for NAT traversal.
""",
        "limitations": """
- NAT traversal needs STUN; corporate networks often need TURN — operational complexity.
- Codec negotiation can be subtle (VP8/VP9/H.264/AV1).
- Browser APIs are mature but mobile native SDK quality varies.
""",
        "cost_notes": "Free protocol.  TURN bandwidth costs (if peers can't connect directly) — coturn self-hosted vs Twilio TURN service.",
        "alternatives": "HLS (cached chunked HTTP, higher latency).  RTSP (legacy, common for IP cameras).  SRT (broadcast-quality, low-latency, less browser support).",
        "references": "https://webrtc.org/; MediaMTX",
    },
    # Resilience libraries
    {
        "slug": "polly",
        "name": "Polly (.NET resilience)",
        "category": "resilience-library",
        "implements_patterns": "retry-with-exponential-backoff-jitter, circuit-breaker, bulkhead, timeout-and-deadline, fallback",
        "tags": "open-source, .net-only, mature",
        "when_to_use": """
ANY outbound HTTP call from a .NET app.

Any external dependency where transient failures are possible.

You want named policies that compose (retry inside circuit-breaker inside bulkhead).

Acme uses Polly named-policy convention — see CLAUDE.md 'Polly named-policy convention.'
""",
        "when_not_to_use": """
You're not on .NET — Resilience4j (Java), Hystrix (legacy Java), failsafe-go.  Each platform has its own.

You're using Polly without configuration — defaults are conservative; tune to your dependency.

You wrap policies around fire-and-forget calls without using cancellation — policies can't cancel what you didn't tell them to.
""",
        "limitations": """
- .NET-only; cross-platform consistency requires equivalent libraries on other stacks.
- Composition order matters: retry inside breaker, NOT breaker inside retry.
- Policy registry can get unwieldy — name conventions matter.
""",
        "cost_notes": "Free open-source.  Tiny runtime overhead.",
        "alternatives": "Resilience4j (Java).  failsafe-go (Go).  Cockatiel (Node — Polly port).  Hand-rolled (don't — get the order wrong and you cascade failures).",
        "references": "https://www.thepollyproject.org/; CLAUDE.md 'Polly named-policy convention' in acme",
    },
    # AI infrastructure
    {
        "slug": "ollama",
        "name": "Ollama",
        "category": "ai-infrastructure",
        "implements_patterns": "tool-use-function-calling, rag-retrieval-augmented-generation, semantic-search-with-embeddings",
        "tags": "self-hosted, offline-capable, open-source, llm-server",
        "when_to_use": """
You want to run open-weight LLMs locally (Llama, Qwen, Mixtral, GPT-OSS, embedding models).

OpenAI-compatible API surface so existing tooling works.

You need embedding generation (nomic-embed-text) without depending on cloud.

Acme / rote uses Ollama on edge-host for the embedding backend and as a delegate for bulk summarization.
""",
        "when_not_to_use": """
You need frontier-model quality (Claude Opus, GPT-4, Gemini) — open weights are getting close but not equal.

You need very high throughput per server — sglang or vLLM are higher-throughput.

JSON-schema-constrained decoding — Ollama supports it but sglang is more reliable.
""",
        "limitations": """
- Multi-model serving on one GPU shares memory — switching models has latency.
- Quantization changes output quality — Q4 vs Q8 matters.
- Smaller models (7B) have meaningful quality gaps from frontier; benchmark before relying.
""",
        "cost_notes": "Free open-source server.  Hardware: a 24GB GPU runs 13B-70B comfortably.  Operational cost: ops time + electricity, vs cloud API per-token billing.",
        "alternatives": "vLLM (higher throughput, more complex setup).  sglang (RadixAttention + schema-guided decoding).  LM Studio (desktop UI + server).  LocalAI (compatibility-focused).",
        "references": "https://ollama.com/; edge-host @ http://edge-host:11434",
    },
    {
        "slug": "sglang",
        "name": "sglang",
        "category": "ai-infrastructure",
        "implements_patterns": "tool-use-function-calling, structured-output-with-schema",
        "tags": "self-hosted, offline-capable, open-source, high-throughput-llm-server",
        "when_to_use": """
You need fast LLM serving with prefix caching (RadixAttention) — RAG with stable system prompts gets huge wins.

JSON-schema-guided decoding that actually obeys the schema (sglang's structured output is reliable).

Multi-turn workloads where the early turns are constant.

Acme uses codec-sglang at http://edge-host:30002 for structured-output tasks.
""",
        "when_not_to_use": """
You want the simplest 'pull a model and chat' experience — Ollama is friendlier.

Single-model serving with infrequent requests — overhead doesn't pay off.

You need vision models with broad coverage — vLLM has broader support today.
""",
        "limitations": """
- More operational complexity than Ollama (compile flags, more knobs).
- Model coverage smaller than vLLM (improving fast).
- Higher GPU memory footprint per model.
""",
        "cost_notes": "Free open-source.  Same GPU hardware as Ollama.",
        "alternatives": "vLLM (similar perf; different tradeoffs).  Ollama (easier).  TGI by HuggingFace (production-leaning).  TensorRT-LLM (NVIDIA-native, highest perf).",
        "references": "https://github.com/sgl-project/sglang",
    },
    {
        "slug": "sqlite-vec",
        "name": "sqlite-vec",
        "category": "vector-db",
        "implements_patterns": "semantic-search-with-embeddings, rag-retrieval-augmented-generation",
        "tags": "embedded, offline-capable, open-source, sqlite-extension",
        "when_to_use": """
You want vector search in an SQLite-based app (this rote).

Single-process embedded search; no separate service to operate.

Tens of thousands to low millions of vectors — sqlite-vec handles this well.
""",
        "when_not_to_use": """
Billions of vectors — use a dedicated vector DB (Qdrant, Milvus, Vespa).

You need distributed query — sqlite-vec is single-process.

You need hybrid search (BM25 + vector) as a built-in — sqlite-vec doesn't ship reranking.
""",
        "limitations": """
- Linear scan for small datasets; ANN index (vec0) for larger.
- Embed dimension fixed at table creation (mean-pool to change).
- Distance metric is cosine by default.
""",
        "cost_notes": "Free open-source.  Zero infra cost beyond the SQLite file.",
        "alternatives": "Qdrant (self-hosted, scales horizontally).  pgvector (Postgres extension; great for shared-DB apps).  Milvus (heavy, scales further).  Chroma (Python-friendly, embedded).",
        "references": "https://github.com/asg017/sqlite-vec",
    },
    # Data stores
    {
        "slug": "postgresql",
        "name": "PostgreSQL",
        "category": "database",
        "implements_patterns": "repository-pattern, outbox-pattern, event-sourcing",
        "tags": "self-hosted, offline-capable, open-source, sql, jsonb",
        "when_to_use": """
General-purpose SQL DB for transactional apps.

You want JSONB columns when domain models have flexible schema (Acme uses jsonb extensively).

LISTEN/NOTIFY for in-DB pub/sub.

Extensions: pgvector for embeddings, PostGIS for geo, TimescaleDB for time-series.

Acme's primary DB.
""",
        "when_not_to_use": """
You need horizontal scale across many writers — Postgres scales to a point; if you need cross-region active-active, look at CockroachDB / YugabyteDB / Spanner.

Pure document store with no relational needs — MongoDB / DynamoDB are simpler for some shapes.

Edge / device storage — SQLite is the answer.
""",
        "limitations": """
- Vertical scale only out of the box (logical replication helps reads; writes scale via partitioning + sharding effort).
- Schema migrations on huge tables need careful planning.
- Connection pooling needs a pooler (PgBouncer) at scale.
""",
        "cost_notes": "Free open-source.  Cloud-managed: AWS RDS / Azure Postgres / Supabase / Neon — pay for compute + storage + IO.",
        "alternatives": "MySQL/MariaDB (similar shape).  SQL Server (.NET-native, commercial).  SQLite (embedded).  CockroachDB (horizontally scalable Postgres-compatible).",
        "references": "https://www.postgresql.org/",
    },
    {
        "slug": "sqlite",
        "name": "SQLite",
        "category": "database",
        "implements_patterns": "repository-pattern, local-first-architecture",
        "tags": "embedded, offline-capable, open-source, sql",
        "when_to_use": """
On-device storage (mobile, edge, IoT, drones).

Single-process server-side cache / log (the rote uses SQLite for audit + anti_patterns + design_patterns + script_run_log).

Test fixtures + ephemeral data.

Local-first apps where the device is the primary owner of the data.
""",
        "when_not_to_use": """
Many concurrent writers (SQLite supports one writer at a time; WAL mode helps but isn't unlimited).

You need network access to the DB — SQLite is file-based.

You need replication / HA out of the box — Litestream and rqlite help but aren't seamless.
""",
        "limitations": """
- Single-writer constraint.
- Schema migration on a running app needs care (PRAGMA user_version, careful ALTER).
- Some extensions (sqlite-vec) need loadable extension support — disabled in some hosts.
""",
        "cost_notes": "Free.  Zero infra.",
        "alternatives": "Postgres (when you need a server).  DuckDB (analytical SQLite).  LMDB / RocksDB (key-value embedded).  Litestream (SQLite + S3 replication).",
        "references": "https://www.sqlite.org/",
    },
    # Auth / identity
    {
        "slug": "authentik",
        "name": "Authentik",
        "category": "identity",
        "implements_patterns": "oidc-pkce, federated-identity",
        "tags": "self-hosted, offline-capable-mostly, open-source, oidc, saml",
        "when_to_use": """
You need a self-hosted OIDC / SAML IdP — Authentik handles both.

You want a clean admin UI for users, applications, groups, policies.

You want flow customization without writing code (consent screens, MFA, captcha).

Acme uses Authentik for OIDC across the SPA, companion, shop, marketing.
""",
        "when_not_to_use": """
You're cloud-only on Azure / AWS / GCP and want a managed IdP (Entra ID / Cognito / Identity Platform).

Your auth needs are tiny — a simple JWT issuer is enough.

Strict regulatory environment where Keycloak's Red Hat backing matters.
""",
        "limitations": """
- Single-process default; HA needs care.
- Authentik blueprints capture config but bootstrapping a fresh tenant needs careful seeding.
- Custom flows are powerful but become tricky to audit.
""",
        "cost_notes": "Free open-source.  Hardware: modest.",
        "alternatives": "Keycloak (more mature, similar feature set, heavier).  Ory Hydra (OAuth2-only; minimal).  Auth0 (managed; expensive).  Entra ID (Azure-locked).",
        "references": "https://goauthentik.io/",
    },
    # MCP infra
    {
        "slug": "metamcp",
        "name": "MetaMCP",
        "category": "mcp-infrastructure",
        "implements_patterns": "mcp-aggregator-proxy, facade-pattern",
        "tags": "self-hosted, offline-capable, open-source, mcp",
        "when_to_use": """
You have multiple downstream MCP servers and want LLM clients to see them through one endpoint.

You want central auth + namespacing across many tool surfaces.

Acme uses MetaMCP on edge-host to aggregate the rote MCP server + others, exposed at /metamcp/{endpoint}/mcp with Bearer auth.
""",
        "when_not_to_use": """
You have only one MCP server — direct connection.

The aggregator adds latency you can't afford.

You don't need cross-tool aggregation, just routing.
""",
        "limitations": """
- Subprocess-launched MCP servers can be flaky to restart.
- Auth is api_key-based today; mTLS would be stronger.
- The aggregator is a SPOF unless replicated.
""",
        "cost_notes": "Free open-source.  Light compute.",
        "alternatives": "Direct MCP connection per client.  Custom proxy with auth middleware.  Future: standardized MCP gateways.",
        "references": "MetaMCP repo; references/metamcp-registration.md",
    },
    # Container / orchestration (just the basics)
    {
        "slug": "docker-compose",
        "name": "Docker Compose",
        "category": "orchestration",
        "implements_patterns": "infrastructure-as-code",
        "tags": "self-hosted, offline-capable, open-source",
        "when_to_use": """
Local-dev or small-prod orchestration (single host).

Multi-service apps where Kubernetes is overkill.

Acme's deploy.cjs ships docker compose stacks for prod.
""",
        "when_not_to_use": """
Multi-host / multi-region orchestration — use Kubernetes / Nomad.

You need rolling updates with zero-downtime invariants out of the box — Compose's update flow is basic.
""",
        "limitations": """
- Single host (or use Swarm which is dead-end).
- Healthcheck dependencies (depends_on: condition: service_healthy) work but are fragile.
- No declarative drift detection.
""",
        "cost_notes": "Free.",
        "alternatives": "Kubernetes (heavy but multi-host).  Nomad (lighter than K8s).  Plain systemd (single host, no containers).",
        "references": "https://docs.docker.com/compose/",
    },
]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def render_design_pattern(p: dict) -> str:
    refs = p.get("references", "")
    return (
        "---\n"
        f"slug: {p['slug']}\n"
        f"name: {p['name']}\n"
        f"category: {p['category']}\n"
        f"intent: {p['intent']}\n"
        f"references: {refs}\n"
        "---\n\n"
        "# When to use\n"
        f"{p['when_to_use'].strip()}\n\n"
        "# When NOT to use\n"
        f"{p['when_not_to_use'].strip()}\n\n"
        "# Structure\n"
        f"{p['structure'].strip()}\n\n"
        "# Example\n"
        f"{p['example_code'].strip()}\n\n"
        "# Relationships\n"
        f"{p['relationships'].strip()}\n"
    )


def render_technology(t: dict) -> str:
    refs = t.get("references", "")
    return (
        "---\n"
        f"slug: {t['slug']}\n"
        f"name: {t['name']}\n"
        f"category: {t['category']}\n"
        f"implements_patterns: {t.get('implements_patterns', '')}\n"
        f"tags: {t.get('tags', '')}\n"
        f"references: {refs}\n"
        "---\n\n"
        "# When to use\n"
        f"{t['when_to_use'].strip()}\n\n"
        "# When NOT to use\n"
        f"{t['when_not_to_use'].strip()}\n\n"
        "# Limitations\n"
        f"{t['limitations'].strip()}\n\n"
        "# Cost\n"
        f"{t.get('cost_notes', '').strip()}\n\n"
        "# Alternatives\n"
        f"{t.get('alternatives', '').strip()}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/path/to/rote")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    dp_dir = root / "design-patterns"
    tech_dir = root / "technologies"

    written = 0
    skipped = 0

    for p in DESIGN_PATTERNS:
        category_dir = dp_dir / p["category"]
        category_dir.mkdir(parents=True, exist_ok=True)
        path = category_dir / f"{p['slug']}.md"
        content = render_design_pattern(p)
        if path.exists() and path.read_text() == content:
            skipped += 1
            continue
        if args.dry_run:
            print(f"[dry-run] would write {path}")
        else:
            path.write_text(content)
            print(f"+ {path}")
        written += 1

    for t in TECHNOLOGIES:
        category_dir = tech_dir / t["category"]
        category_dir.mkdir(parents=True, exist_ok=True)
        path = category_dir / f"{t['slug']}.md"
        content = render_technology(t)
        if path.exists() and path.read_text() == content:
            skipped += 1
            continue
        if args.dry_run:
            print(f"[dry-run] would write {path}")
        else:
            path.write_text(content)
            print(f"+ {path}")
        written += 1

    print(f"\n{written} written, {skipped} unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
