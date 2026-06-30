---
slug: source-agnostic-relay
name: Source-agnostic relay (pluggable ingress -> constant encrypted egress)
category: architectural
intent: Relay video/data from ANY source through one node to a secure upstream by making the source a pluggable strategy while the egress stays constant and encrypted
references: apps/companion/docs/video-relay-architecture.md; feedback_companion_is_transparent_relay
---

# When to use
A relay node (e.g. a companion phone) must accept many input kinds — phone camera,
USB/UVC capture, RTSP IP-cams, RTMP-only clients (DJI), SRT — and forward them to a
secure upstream. Model each source as a strategy (an `IVideoSource` / discriminated
union); keep ONE egress (e.g. WHIP/WebRTC-over-TLS, or rtmps). New source = new
strategy; egress untouched.

# When NOT to use
A single fixed source feeding a single sink — just wire them directly.

# Why it wins
- Security invariant for free: if the egress is ALWAYS encrypted, a source may be
  plaintext LOCALLY (DJI -> rtmp://127.0.0.1) and nothing cleartext ever leaves the
  device. "No plaintext on the wire" then holds for every source automatically.
- One auth/identity path, one bitrate/codec policy, one place to add channels.
- Mirrors registry-per-pivot discipline (Sensor vs Transport registries).

# Implementation note
Sources that can't yield the egress's native medium (e.g. an RTMP byte stream can't
become a WebRTC MediaStream without native transcode) take a sibling encrypted
transport instead — e.g. an RTMP->rtmps forward (snippet ffmpeg-rtmp-to-rtmps-relay).
Still the same pattern: constant *encrypted* egress, the transport just differs by
source capability. Route that source to its own publisher, exactly as a relay path
is routed separately from the camera path.
