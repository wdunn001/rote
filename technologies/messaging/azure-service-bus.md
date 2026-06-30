---
slug: azure-service-bus
name: Azure Service Bus
category: messaging
implements_patterns: queue-based-load-leveling, outbox-pattern
tags: cloud-only, managed, vendor-locked, no-offline
references: https://learn.microsoft.com/azure/service-bus-messaging/
---

# When to use
Pure-cloud Azure-native apps that have NO offline requirement.

You want managed: no broker ops, AAD-integrated auth, SLAs.

Standard cross-region replication is nice to have.

# When NOT to use
**Offline / edge / on-prem deployment** — Service Bus is cloud-only.  Acme explicitly DOES NOT USE Service Bus because devices, drones, and the GCS bundle must work disconnected.

Multi-cloud or vendor-lock-averse architectures.

Tight cost control — Service Bus charges per operation; at scale it's expensive.

# Limitations
- Cannot run on-prem or in offline scenarios — that's the binding limitation for Acme.
- Vendor lock — Service Bus topics + subscriptions aren't trivially portable to other brokers.
- Per-message + per-connection charges; large fan-out gets expensive.

# Cost
Standard tier: ~$10/mo for low volume, but scales fast.  Premium tier: $677+/month per messaging unit — for HA + dedicated resources.

# Alternatives
RabbitMQ self-hosted (works offline; lower ongoing cost; you operate it).  AWS SQS/SNS (same cloud-only limitation).  NATS (self-hosted, simpler than RabbitMQ).
