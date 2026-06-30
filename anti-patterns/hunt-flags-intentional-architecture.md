---
slug: hunt-flags-intentional-architecture
title: Security-hunt tooling flagging intentional architecture as findings (alarm fatigue)
hit_count: 1
token_cost: medium - false-HIGH findings waste the owner's time, erode trust in the whole report, and bury the real items
---

# Symptom

A hunt/scan rates owner-intended design as a vulnerability and the owner has to push
back: "what's wrong with this? it's intentional." Examples seen:
- Services bound to `0.0.0.0` rated "HIGH / public" when the perimeter forwards only
  80/443 and the internal LAN is trusted - all-interfaces is **LAN-reachable, not
  internet-public**.
- A Docker-management tool (Portainer) mounting `docker.sock` rated "host-takeover
  surface" when socket access IS its function and it is LAN-only by design.
- Home Assistant `privileged` rated a finding when it needs hardware access.
- Every container "running as root (default)" flagged - true but noise.

# Root cause

The tool applied a single worst-case (zero-trust, internet-exposed) threat model
instead of the asset's actual one. Severity is a function of THREAT MODEL
(who can reach it, what the perimeter allows, what the component is for), not of
the raw attribute. "all-interfaces", "has the docker socket", "privileged",
"runs as root" are attributes, not verdicts.

# Remedy

- **Establish the threat model first**: is the LAN trusted? what does the perimeter
  forward inbound? is this host segmented? Ask, or state the assumption explicitly.
- **Label attributes as attributes**: emit `NOTE: <svc> on all-interfaces (LAN-reachable)`
  not `FLAG: public`. Make severity conditional ("a finding ONLY IF the LAN is
  untrusted OR the perimeter forwards this port").
- **Treat by-design infra as by-design**: a management tool with the socket, an
  automation container with hardware access, a reverse-proxy with the socket for
  discovery - note them, don't condemn them.
- **Reserve HIGH** for things that are wrong under the owner's OWN model (e.g. an
  unexpected listener, an unknown SSH key, a service exposed THROUGH the perimeter,
  an unpatched internet-facing RCE).
- When corrected, recalibrate the report AND the tool wording so the next run is right.

# Detection

Owner says "that's intentional" / "what's wrong with that?" more than once, or a
report's HIGH list is dominated by long-standing deliberate config. That is the tell
to recalibrate to the actual threat model.

# See also

- [[rote]] skill
- nix-hunt.sh / win-vuln-config-audit.ps1 (calibrate listener + posture severity to threat model)
