# Open Questions

All questions have been resolved.

## Resolved

### OQ-001: Registration fee lifecycle

Decision: ADR-003 — Copy from Chama as OWED at membership creation.

### OQ-002: Contribution period

Decision: ADR-004 — Calendar month `YYYY-MM` string.

### OQ-003: Share formula

Decision: ADR-005 — `units = amount / SHARE_UNIT_PRICE` per contribution.

### OQ-004: Role rules

Decision: ADR-006 — Default MEMBER; up to one leadership role per
membership; one CHAIRPERSON per Chama; CHAIRPERSON manages all roles.

### OQ-005: Identity uniqueness

Decision: ADR-007 — Phone and government ID globally unique.

### OQ-006: Chama access model

Decision: ADR-008 — Creator becomes member + chairperson.

### OQ-007: Contribution statuses

Decision: ADR-009 — PENDING/CONFIRMED/REVERSED; no physical deletion.

### OQ-008: User-to-member identity linking

Decision: ADR-008 addendum — `POST /api/v1/auth/me/member-link` claims an
existing member matching the user's supplied `phone_number` and
`government_id`.

### OQ-009: Multiple accounts for one Member (P0 security fix)

Decision: One Member may be linked to only one User account. Enforced with
`UNIQUE (users.member_id)` and a `409` when a second account attempts to
claim an already-claimed member.

### OQ-010: Government-ID exposure

Decision: Chama/membership views return members without `government_id`
(public member schema). Full government IDs are only available to the user
whose own member record they belong to via the auth endpoints.

### OQ-011: JWT secret fail-closed

Decision: Outside development mode (`CHAMACORE_DEBUG=false`),
`CHAMACORE_JWT_SECRET_KEY` must be set; the known default secret is rejected
at configuration load.
