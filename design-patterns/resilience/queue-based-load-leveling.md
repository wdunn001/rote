---
slug: queue-based-load-leveling
name: Queue-Based Load Leveling
category: resilience
intent: Decouple producers from consumers via a queue so spikes don't overwhelm downstream
references: Microsoft Azure 'Queue-Based Load Leveling pattern'
---

# When to use
Producer burst rate >> consumer steady rate (a thousand telemetry samples land in 1 second; the analyzer processes 100/s).

Producer and consumer have different scaling characteristics.

Failures on the consumer side shouldn't block producers (the queue absorbs).

# When NOT to use
The operation is genuinely synchronous (the producer needs the result to continue).  Don't queue what you need now.

The queue grows unboundedly and you've not addressed the underlying mismatch — added latency, not solved a problem.

# Structure
Producer enqueues fire-and-forget.  Queue (RabbitMQ, ServiceBus, SQS, in-proc Channel) buffers.  Consumer dequeues at its own pace, with retry on failure (often dead-letter on max retries).

# Example
```csharp
// Producer
await _channel.Writer.WriteAsync(new TelemetrySample(...));

// Consumer (background service)
await foreach (var sample in _channel.Reader.ReadAllAsync(ct)) {
    await _processor.HandleAsync(sample, ct);
}
```

# Relationships
Pairs with bulkhead (one consumer pool per queue).  Foundation of background-processing / worker patterns.  Pairs with outbox-pattern for guaranteed delivery.
