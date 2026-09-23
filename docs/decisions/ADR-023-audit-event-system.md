# ADR-023: Append-Only Business Audit Event System

## Status

Approved 2026-09-23 (scale-report step 9; decision D-08 from
`OPEN_QUESTIONS.md`).

Implemented 2026-09-23: `app/models/audit_event.py`, `app/repositories/
audit.py`, `app/services/audit.py`, append-only trigger guards
`app/db/audit_guards.py`, API router `app/api/v1/audit.py`, migration
`9a8b7c6d5e4f`, events wired into auth, chama, membership, role,
contribution, and payment-connection operations, and
`tests/test_audit_events.py`.

## Context

The financial ledger answers *"what happened financially?"*; no dedicated
system answers *"who performed the action, when, and against what
resource?"*. `reports/latestreport.md` (spec §19–§21) requires a separate,
append-only business audit event system. Decision D-08 was recorded in
`OPEN_QUESTIONS.md` and ratified by the product owner.

## Decision

### Storage and fields

A new `audit_events` table stores one append-only row per audited action:

```text
id, chama_id (nullable), actor_user_id (nullable), action, resource_type,
resource_id (nullable), request_id, metadata (JSON), success, ip_address,
user_agent, created_at
```

`actor_user_id` and `chama_id` are nullable so failed authentications
(actor unknown) and identity-claim events outside any Chama can still be
recorded. `metadata` is a small JSON document; it may never contain secrets,
passwords, access tokens, refresh tokens, payment credentials, or encrypted
credential material (spec §19/§41). `request_id` is the active request
correlation id (`app.core.logging.get_request_id()`).

The action and resource type are stored as constrained strings (a closed
set of constants in the audit service), and `success` records whether the
operation finished successfully.

### Append-only protection

Audit events are immutable evidence:

- no application endpoint can update or delete audit events (no `PUT` or
  `DELETE`);
- database `BEFORE UPDATE`/`BEFORE DELETE` triggers on `audit_events`
  reject modifications at the database level on both SQLite and PostgreSQL
  (installed by the migration and extended into `app/db/audit_guards.py`,
  created by the same migration and the test harness).

### Scope (D-08)

Record the spec §20 action list for the operations that exist:

- authentication: login, failed login, logout, refresh, identity claim
  (member link);
- membership: member creation, status change;
- roles: role assignment, role removal;
- contributions: creation, confirmation, reversal;
- loans: application, approval, rejection, disbursement, repayment, repayment
  reversal (ADR-020);
- payouts: request, approval, rejection, processing, completion, failure,
  reversal (ADR-021);
- registration fees: payment, payment reversal, waiver (ADR-022);
- payment configuration: payment connection creation/activation/suspension/
  credential replacement, C2B registration;
- administrative: Chama creation, Chama update, Chama status change.

The shorthand used by the `Authorization` failure paths above must not mask
the fact that *failed* actions (e.g. rejected login, rejected permission
checks on audited endpoints) are also recorded when they are part of the
listed action set — for example an unauthorized attempt to confirm a
contribution still emits a `contribution.confirm` event with
`success=false`.

### Read access

`GET /api/v1/chamas/{chama_id}/audit-events` returns the Chama's events to
any active member, mirroring the existing read model for other
Chama-scoped financial/history resources (contributions, ledger,
memberships). Cross-Chama reads are impossible: events are always filtered
by the authenticated actor's Chama membership.

## Consequences

- Sensitive actions now produce immutable, replayable evidence whose
  identity fields (actor, resource, request id, IP, user agent) are captured
  without storing secrets.
- Scale-report step 9 and completion-spec Phase 6 are unblocked.
- The audit system is separate from the ledger; it records *who/what/when*,
  while the ledger remains the sole financial source of truth.