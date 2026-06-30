---
slug: webrtc
name: WebRTC
category: realtime
implements_patterns: peer-to-peer, low-latency-media
tags: browser-native, p2p, low-latency, complex
references: https://webrtc.org/; MediaMTX
---

# When to use
Sub-second media latency (drone live video, voice/video calls, screen share).

Peer-to-peer with optional TURN relay — the data flows direct between peers when possible.

You're publishing to WHIP/WHEP-compatible servers (MediaMTX in Acme).

# When NOT to use
File transfer / async data — use HTTP.

You need centralized recording / transcoding without a media server in the path — WebRTC alone is peer-to-peer.

You can't afford STUN/TURN infra for NAT traversal.

# Limitations
- NAT traversal needs STUN; corporate networks often need TURN — operational complexity.
- Codec negotiation can be subtle (VP8/VP9/H.264/AV1).
- Browser APIs are mature but mobile native SDK quality varies.

# Cost
Free protocol.  TURN bandwidth costs (if peers can't connect directly) — coturn self-hosted vs Twilio TURN service.

# Alternatives
HLS (cached chunked HTTP, higher latency).  RTSP (legacy, common for IP cameras).  SRT (broadcast-quality, low-latency, less browser support).
