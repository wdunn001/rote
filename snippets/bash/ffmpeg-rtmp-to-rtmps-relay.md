---
slug: ffmpeg-rtmp-to-rtmps-relay
name: ffmpeg as a loopback RTMP-server -> rtmps relay (no transcode)
language: bash
applies_patterns: source-agnostic-relay
applies_technologies: ffmpeg, mediamtx
references: apps/companion/modules/mz-rtmp-relay; anti-pattern archived-native-dependency-vanished
---

# When to use
Accept a plaintext RTMP publisher that cannot do TLS (e.g. DJI Fly) and re-publish
it ENCRYPTED (rtmps) with NO transcode. ffmpeg runs the RTMP server (-listen 1) and
copy-forwards the FLV. Same idea works server-side or on-device (via an ffmpeg-kit
native module).

# When NOT to use
You need to transcode/re-encode (drop -c copy then). Or you can't obtain an ffmpeg
build with rtmp+rtmps+flv+TLS — ffmpeg-kit is archived (see anti-pattern
archived-native-dependency-vanished); vendor a prebuilt AAR or use a maintained build.

# Placeholders
- LOCAL_PORT: loopback RTMP server port (example: 1935)
- APP: rtmp app segment the publisher targets (example: live)
- TARGET_RTMPS: rtmps publish URL incl. token (example: rtmps://host:1937/companion/ID?token=JWT)

# Snippet
ffmpeg -hide_banner -loglevel warning \
  -listen 1 -rtmp_listen 1 -i "rtmp://127.0.0.1:${LOCAL_PORT}/${APP}" \
  -c copy -f flv "${TARGET_RTMPS}"
# -listen 1 makes the rtmp INPUT a server (waits for a publisher); -c copy -f flv
# re-muxes the same FLV straight to the rtmps output (no transcode). When invoking
# via FFmpegKit, use the ARGS-ARRAY form (not a joined string) so the ?token=...&...
# query is passed verbatim. UNVERIFIED on-device: confirm -listen mode is honored +
# the token query survives ffmpeg's rtmp tcUrl/playpath split on your build.
