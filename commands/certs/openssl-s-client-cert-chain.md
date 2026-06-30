---
slug: openssl-s-client-cert-chain
name: openssl s_client -showcerts (inspect cert chain)
family: certs
platform: cross-platform
equivalents: curl -v --cacert <ca> https://host (less detail)
references: man s_client
---

# Command
```sh
openssl s_client -showcerts -connect <host>:443 -servername <host> < /dev/null
```

# When to use
Inspect the full TLS handshake + cert chain a server presents. Diagnose 'why does my client say this cert is invalid'.

# When NOT to use
Quick cert info — `openssl x509 -text -in <file>` on a downloaded cert is faster.
Production monitoring — Prometheus exporters / managed cert monitoring exist for that.

# Gotchas
- WITHOUT `-servername <host>`, SNI isn't sent, and you may get the default cert instead of the one for your host.
- `< /dev/null` closes stdin so s_client doesn't hang waiting for your HTTP request.
- The chain is presented bottom-up: leaf cert first, then intermediates. The root is usually NOT in the chain (the client validates against its own trust store).
- For just the chain: `openssl s_client ... | sed -n '/-----BEGIN CERTIFICATE-----/,/-----END CERTIFICATE-----/p'`
- This is exactly the test that verified the Acme device cert chain (G1.1/G1.2/G1.4.a/G1.6 in CLAUDE.md).

# Flags
- `-connect <host:port>`: target
- `-servername <host>`: SNI
- `-showcerts`: dump full chain (not just leaf)
- `-CAfile <ca-bundle>`: use a specific CA bundle
- `-verify_return_error`: exit non-zero on verify fail
- `-tls1_3` / `-tls1_2`: force a TLS version

# Examples
- Standard: `openssl s_client -showcerts -connect app.acmefpv.com:443 -servername app.acmefpv.com < /dev/null`
- Extract just cert PEMs: `openssl s_client ... < /dev/null 2>/dev/null | openssl x509 -outform PEM > leaf.pem`
- Test custom CA: `openssl s_client ... -CAfile /etc/ssl/certs/my-root.pem`
