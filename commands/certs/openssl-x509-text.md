---
slug: openssl-x509-text
name: openssl x509 -text -noout -in <cert>
family: certs
platform: cross-platform
equivalents: step certificate inspect <cert>
references: man x509
---

# Command
```sh
openssl x509 -text -noout -in <cert.pem>
```

# When to use
Inspect a downloaded cert's subject / issuer / SANs / validity / extensions / signature algorithm.

# When NOT to use
JWT or other non-X509 token — use `jwt-cli` or `jq`.

# Gotchas
- `-noout` SUPPRESSES the PEM dump at the end. Without it you get human-readable PLUS the PEM (ugly).
- The cert must be in PEM format (BEGIN CERTIFICATE / END CERTIFICATE). For DER: `-inform DER`.
- For chain files: each cert is rendered separately; use `awk` or `csplit` to split.
- The 'Subject Alternative Name' line is where hostname matching happens. CN (Common Name) is largely deprecated.

# Flags
- `-text`: human-readable
- `-noout`: don't include the PEM
- `-in <file>`: input
- `-inform PEM|DER`: input format
- `-subject` / `-issuer` / `-dates` / `-fingerprint`: just one field
- `-purpose`: what this cert is good for (server / client / signing)

# Examples
- Inspect: `openssl x509 -text -noout -in /etc/ssl/certs/my.crt`
- Just the SAN line: `openssl x509 -text -noout -in cert.pem | grep -A1 'Subject Alternative Name'`
- Just dates: `openssl x509 -dates -noout -in cert.pem`
- DER input: `openssl x509 -inform DER -in cert.der -text -noout`
