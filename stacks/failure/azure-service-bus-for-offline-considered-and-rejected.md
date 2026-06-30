---
slug: azure-service-bus-for-offline-considered-and-rejected
name: Azure Service Bus for an offline-required pipeline (considered, REJECTED)
technologies: azure-service-bus
patterns: queue-based-load-leveling, outbox-pattern
context: Acme — drone telemetry + companion offline queue
outcome: failure
references: See technology entry: azure-service-bus
---

# What worked
- Service Bus is genuinely well-designed for cloud-native queueing
- Managed; you don't operate the broker
- AAD integration is clean

# What didn't
- Doesn't work offline.  Period.  No on-prem option.  No edge deployment.
- Drones, companion phones in the field, and the GCS bundle MUST work without cloud connectivity — Service Bus is a non-starter
- Cost scales per-message; high-fanout telemetry would be expensive

# When to reuse
- Pure cloud-native Azure workloads with NO offline requirement

# When to avoid
- ANY Acme use case — devices and the GCS bundle are offline-survivable by design.
- Multi-cloud / vendor-lock-averse architectures.
