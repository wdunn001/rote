---
slug: mosquitto
name: Eclipse Mosquitto
category: messaging
implements_patterns: observer, queue-based-load-leveling
tags: self-hosted, offline-capable, open-source, mqtt, lightweight
references: https://mosquitto.org/
---

# When to use
You need a lightweight MQTT broker for IoT devices.

You want a tiny operational footprint — Mosquitto runs on a Raspberry Pi.

You don't need AMQP / Kafka semantics — MQTT pub/sub is enough.

Acme uses Mosquitto colocated at deploy/mosquitto.conf for the public MQTT surface (mqtt.<domain>:8883).

# When NOT to use
You need durable per-subscriber queues (MQTT5 helps but Mosquitto's persistence is simpler than RabbitMQ's).

You need cross-protocol bridging — RabbitMQ MQTT plugin is more flexible.

You need clustering with strong consistency — Mosquitto is single-instance by default.

# Limitations
- Single-process; no HA built-in (use replication carefully).
- Persistence is a flat file — not designed for huge backlogs.
- Security model is per-username/password + ACL; works but feels dated next to OAuth/mTLS-native brokers.

# Cost
Free open-source.  Negligible compute.

# Alternatives
RabbitMQ MQTT plugin (full AMQP+MQTT broker).  EMQX (commercial, higher scale).  HiveMQ (commercial).  AWS IoT Core (managed, NOT offline-capable for the broker itself).
