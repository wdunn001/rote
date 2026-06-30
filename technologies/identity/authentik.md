---
slug: authentik
name: Authentik
category: identity
implements_patterns: oidc-pkce, federated-identity
tags: self-hosted, offline-capable-mostly, open-source, oidc, saml
references: https://goauthentik.io/
---

# When to use
You need a self-hosted OIDC / SAML IdP — Authentik handles both.

You want a clean admin UI for users, applications, groups, policies.

You want flow customization without writing code (consent screens, MFA, captcha).

Acme uses Authentik for OIDC across the SPA, companion, shop, marketing.

# When NOT to use
You're cloud-only on Azure / AWS / GCP and want a managed IdP (Entra ID / Cognito / Identity Platform).

Your auth needs are tiny — a simple JWT issuer is enough.

Strict regulatory environment where Keycloak's Red Hat backing matters.

# Limitations
- Single-process default; HA needs care.
- Authentik blueprints capture config but bootstrapping a fresh tenant needs careful seeding.
- Custom flows are powerful but become tricky to audit.

# Cost
Free open-source.  Hardware: modest.

# Alternatives
Keycloak (more mature, similar feature set, heavier).  Ory Hydra (OAuth2-only; minimal).  Auth0 (managed; expensive).  Entra ID (Azure-locked).
