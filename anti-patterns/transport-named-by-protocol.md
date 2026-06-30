---
slug: transport-named-by-protocol
title: Naming a transport after the protocol it carries (e.g. MavlinkTransport instead of BleTransport)
hit_count: 4
token_cost: medium — locks the design; future protocol changes require renaming + grepping; protocol negotiation becomes impossible
---

# Symptom

You see types like `MavlinkBleTransport`, `MspWifiTransport`, `BleGattMavlinkLink`, or APIs like `mavlinkTransport.send(...)`. The protocol name (MAVLink / MSP / CoT) is baked into the class/file/variable name.

# Root cause

Transports (BLE, WiFi-TCP, USB, MQTT, multicast UDP) carry bytes. Protocols (MAVLink, MSP, CoT, JSON ingest) are the structure of those bytes. The same firmware/device often supports multiple protocols on the same transport — protocol gets **negotiated at runtime** (firmware family detection, capability handshake). Hardcoding the protocol into the transport's name means:

1. Adding a new protocol on the same transport requires creating a parallel class and grep-renaming.
2. Negotiating protocol at runtime becomes awkward — the type name lies.
3. Tests / mocks proliferate (`MockMavlinkBleTransport`, `MockMspBleTransport`).

# Remedy

Name transports by transport: `BleTransport`, `WifiTcpTransport`, `UsbSerialTransport`, `MqttTransport`. The protocol is a runtime concern handled by a `ProtocolCodec` layer above the transport. The Strategy/Router (see `gcs_link.h` in mz-pid-tuner) inspects the device's firmware family at connect time and selects MAVLink-vs-MSP-vs-MAVLink2 dynamically.

# Detection

If you find yourself writing `XxxxYyyyTransport` where Xxxx is a protocol name and Yyyy is a transport name, **swap the order in your head**: protocol is the cargo, transport is the truck. The truck class name doesn't change when the cargo does.

# See also

- [[feedback-transport-not-protocol-naming]]
- [[arch-fc-protocol-vs-family]]
