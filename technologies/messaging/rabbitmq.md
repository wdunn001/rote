---
slug: rabbitmq
name: RabbitMQ
category: messaging
implements_patterns: queue-based-load-leveling, outbox-pattern, observer
tags: self-hosted, offline-capable, open-source, amqp, mqtt-bridge
references: https://www.rabbitmq.com/
---

# When to use
You need a self-hostable durable message broker that can run on edge / on-prem / in your own cloud.

You want flexible routing (topics, fanout, direct exchanges, headers).

You need MQTT (for IoT devices) AND AMQP (for cloud apps) on the same broker — RabbitMQ does both.

Acme uses RabbitMQ for cot-bridge ↔ broker ↔ API and as the MQTT broker for DeviceA cellular bridges.

# When NOT to use
You need ordering across all messages (Kafka is built for that, RabbitMQ isn't).

Throughput requirements >100k msg/s sustained — RabbitMQ tops out; Kafka or Pulsar scale higher.

You don't want to operate it — managed alternatives exist but the offline-capable story disappears.

# Limitations
- Routing logic complexity grows fast — keep it documented.
- Single-broker mode is a SPOF; clustering exists but adds operational weight.
- AMQP 0-9-1 is the common protocol; AMQP 1.0 support is partial.

# Cost
Free open-source.  Hardware: a small broker handles 10k msg/s on commodity hardware.  Operational cost: real but manageable.

# Alternatives
Apache Kafka (higher throughput, ordered streams; harder to operate).  NATS (lighter, simpler).  Azure Service Bus / AWS SQS (managed, but NOT offline-capable).  Mosquitto (MQTT-only).
