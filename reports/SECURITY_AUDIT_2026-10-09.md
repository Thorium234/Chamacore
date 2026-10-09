# ChamaCore Security Audit — 2026-10-09

## Scope

Review of the FastAPI backend and Next.js consumer UI focused on identity,
Chama tenancy, payments, sessions, callback intake, browser security, and
deployment configuration. This source audit does not replace live testing.

## Remediated in this change

| Priority | Finding | Risk | Change made |
| --- | --- | --- | --- |
| High | Chama founding policy could split one person into several identities. | Requiring another phone/account would fragment a person's memberships and financial history. | A linked Member may now found multiple Chamas through separate Membership rows; phone number and government ID remain globally unique. |
| High | Password changes did not revoke refresh tokens. | A stolen refresh token could continue a session after password reset. | Password changes now revoke all refresh tokens in the same committed operation. |
| Medium | Password checks did not compare member phone numbers. | A predictable phone-derived password could be accepted. | Registration and password change now validate against the canonical phone number. |
| Medium | Client request IDs were unbounded. | Log and audit pollution or storage errors. | Values over 64 characters are replaced with a server-generated ID. |
| Medium | Configuration templates had duplicate database settings and an invalid comma-separated callback base URL. | Wrong database selection or invalid payment callback URLs. | Templates now use one explicit local value and document production replacement. |
| High | A deactivated account could keep using an issued access token until expiry. | Support lockouts were incomplete during an incident. | Authentication now rejects inactive accounts on every authenticated request. |
| Medium | Browser hardening headers were missing. | Framing and unnecessary device API use. | Next.js and production API responses now include baseline hardening headers. |

## Findings requiring follow-up

| Priority | Finding | Recommended remediation |
| --- | --- | --- |
| High | Refresh tokens are in browser localStorage and can be stolen by successful same-origin script injection. | Move refresh tokens to Secure, HttpOnly, SameSite cookies behind a same-origin BFF or cookie API. Add CSRF protection. |
| High | Frontend runtime dependencies currently include known Next.js, Sharp, and source-map-js advisories. | Cache poisoning, image optimizer SSRF, disclosure, and denial of service. | Upgrade Next.js and the matching ESLint config to 16.4.0 or newer, regenerate the lockfile, and enforce npm audit --omit=dev in CI. The local installer stalled before it could update the lockfile, so this item is not marked fixed. |
| High | Government IDs are initial member passwords under the current product rule. | Replace with a cryptographically random, single-use setup token delivered through a verified channel. |
| High | Callback body size is checked after FastAPI reads the request body. | Enforce limits at the reverse proxy and add streaming ASGI limits for callback routes. |
| Medium | Rate limits are in-process and depend on request.client.host. | Apply rate and body limits at the edge, configure trusted proxy headers, and use shared limiting before multiple workers. |
| Medium | The UI has no Content-Security-Policy. | Implement a nonce-based CSP compatible with Next.js, then restrict script, connect, image, and frame sources. |
| Medium | SQLite is not a production financial database. | Use PostgreSQL with backups, encrypted transport, least-privilege credentials, migration rehearsal, and restore tests. |
| Medium | Provider callback authenticity needs deployment confirmation. | Use HTTPS, source restrictions and provider signature verification where available, rotate callback tokens, and alert on replay or disagreement events. |
| Low | CORS can be weakened through deployment configuration. | Maintain a reviewed explicit origin allowlist and reject wildcard values at startup. |

## Existing controls confirmed

- Chama-scoped services authorize active membership before data access.
- Membership public responses omit government IDs.
- Payment attempts use idempotency keys, provider IDs, callback deduplication, and ledger-backed settlement.
- Refresh tokens are hashed at rest, single-use, and rotate on refresh.
- Production disables interactive API documentation and protects metrics.

## Identity and Chama-founding rule

A linked user may found multiple Chamas with the same Member identity. Each
Chama receives a separate Membership, while phone number and government ID
remain globally unique to prevent duplicate identities for one person.

## Verification checklist

1. Confirm a registered identity can create multiple Chamas with the same Member.
2. Confirm the same Member can be added to a second Chama using matching phone and government ID.
3. Confirm adding that Member twice to the same Chama returns 409.
4. Confirm profile and onboarding continue to show creation for normal members.
5. Set production secrets, PostgreSQL, HTTPS, and edge request limits before handling live funds.
