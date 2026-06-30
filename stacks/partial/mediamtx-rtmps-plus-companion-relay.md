---
slug: mediamtx-rtmps-plus-companion-relay
name: MediaMTX rtmps ingest + companion source-agnostic relay
technologies: mediamtx, ffmpeg, expo, react-native-webrtc
patterns: source-agnostic-relay
context: Acme — secure drone video ingest (rtmps for capable encoders + relay for rtmp-only DJI)
outcome: partial
references: project_acme_secure_streaming; apps/companion/docs/video-relay-architecture.md
---

# What worked
- MediaMTX `rtmpEncryption: optional` serving plaintext 1935 + rtmps 1937, TLS from
  the existing acme-companion LE cert mounted read-only out of the shared
  `nginx-proxy-certs` volume into the mediamtx container at /certs. Clean, no extra
  cert tooling.
- rtmps URL minting + the HTTP-auth callback reading the token from the URL QUERY
  (RTMP carries `?token=` in the query, not a header) — that was the real auth bug.
- A DEDICATED TLS port (1937) beat SNI-multiplexing on 443: 443 already binds the
  http server, so a stream ssl_preread there would mean fronting the whole web edge.
  A dedicated port matched the existing 8189/udp ICE forward pattern — low risk.

# What didn't (at first) — then resolved
- ffmpeg-kit is ARCHIVED and its native binaries were purged from Maven Central / npm /
  CocoaPods on 2025-04-01. The JitPack coordinate (com.github.arthenica:ffmpeg-kit:v6.0)
  RESOLVES but is a 56K Java-only stub with ZERO .so — JitPack only rebuilds the wrapper,
  never the hours-long NDK native build. So the relay was dead on arrival.
- RESOLUTION: the exact original native AAR (com.arthenica:ffmpeg-kit-https:6.0-2.LTS,
  46.9 MB, all 4 ABIs, gnutls+rtmps+flv VERIFIED) still lives on Aliyun's public maven
  mirror (maven.aliyun.com/repository/public) — purged-from-official ≠ gone. Vendored
  into modules/mz-rtmp-relay/android/libs/ and consumed via flatDir + implementation(
  name:..., ext:'aar'). No NDK build needed. See anti-pattern
  archived-native-dependency-vanished for the mirror-hunt playbook.
- A NAT/router port-forward to the plaintext port does NOT provide rtmps (no TLS
  termination). See anti-pattern nat-port-forward-does-not-terminate-tls.
- DJI Fly can't do rtmps at all, so it MUST relay on the phone (loopback rtmp -> rtmps)
  — the conversion has to happen before the internet hop or it's plaintext on the wire.

# When to reuse
- Multi-protocol live ingest where SOME clients can't do TLS: terminate/encrypt at
  the server (rtmps listener with the LE cert) for capable encoders, and relay the
  rtmp-only clients locally on a node near them.

# When to avoid
- If you can't source a maintained ffmpeg (or equivalent) for the relay half, the
  rtmp-only-client path stays blocked — don't promise that path until the engine is real.
