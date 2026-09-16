# V3 — Payment Architecture — Design

Status: Implemented. V3 payment architecture is complete.

## Goal

V3 gives ChamaCore a secure, audited payment architecture that integrates with
real Kenyan payment providers (Jenga/Finserve and Safaricom Daraja) without
leaking provider details into the domain layer. The system issues STK Push
requests, tracks attempts, and ingests provider callbacks into a deduplicated,
append-only event inbox.

## Scope (this increment)

This increment delivers:

- The provider port and adapter boundary (ADR-016).
- The payment connection lifecycle (ADR-017).
- The payment intent and attempt state machines.
- The webhook inbox and event deduplication (ADR-018).
- A database migration adding 6 V3 tables and associated indexes.
- Full test suites: credential cipher, connection lifecycle, intent/attempt
  orchestration, webhook inbox, and adapter contract tests with mocked HTTP.

## Provider port and adapters

See ADR-016.

`app/providers/base.py` defines `ProviderPort`, the single interface the
payment domain depends on. Concrete adapters implement provider-specific HTTP
calls:

- `JengaAdapter` — Finserve Africa api-checkout STK Push.
- `DarajaAdapter` — Safaricom Lipa Na M-Pesa STK Push.

A `ProviderRegistry` keyed by `(provider_code, environment)` ensures sandbox
connections can never reach production endpoints.

Adapters are independently testable via `httpx.MockTransport` without
touching a live provider API (53 contract tests).

### Documented limitations

- Jenga IPN payload/signature contract is merchant-specific; the adapter
  relies on attempt binding and callback tokens for security.
- Daraja provides no per-payload signature or hash; the same controls apply.

## Connection lifecycle

See ADR-017.

Connections are unique per `(chama, provider, environment)`. Credentials are
sealed with AES-256-GCM and never exposed. The lifecycle:

```
PENDING_VALIDATION ──validate()──> ACTIVE
                 └──validate(fail)──> INVALID
                 └──disable()──> DISABLED
                 └──replace()──> PENDING_VALIDATION (new version)
```

- Chairperson-only mutations: create, replace, disable, delete.
- Delete is blocked when financial history (attempts or events) exists.
- Validation is rate-limited; disables are idempotent.
- Audit trail: every transition appends a `PaymentConnectionAudit` row.

## Intent and attempt model

A `payment_intent` is a request to collect a fixed KES amount from one
member, expressed as a purpose and amount tied to a `membership`. Intents are
idempotent by `(chama_id, idempotency_key)` with payload hash matching.

An intent progresses through:

```
PENDING → PROCESSING → SUCCEEDED
                     → FAILED
```

State transitions are enforced: `PENDING` only enters `PROCESSING` when an
attempt is initiated; `PROCESSING` reaches `SUCCEEDED` or `FAILED`; terminal
states have no outgoing transitions.

A `payment_attempt` is a single STK Push call made against an ACTIVE
connection. Attempts are numbered sequentially and at most one attempt is in
flight at a time.

- `initiate()` orchestrates the single retry cycle: first attempt, or a
  retry after a transient failure, within retry limits.
- A `PERMANENT_FAILURE_CODES` frozenset prevents retrying known non-retryable
  provider errors (insufficient balance, cancelled by customer).
- A `ProviderTimeoutError` returns a `TIMEOUT` attempt with no
  `provider_request_id`; a subsequent `initiate()` returns the same TIMEOUT
  attempt (no duplicate call made).

Each attempt stores a `provider_transactions` row that records the
normalized status and raw response from the provider, enabling offline query
resolution when the webhook is late or missing.

## Webhook inbox

See ADR-018.

`POST /api/v1/payments/webhooks/{provider_code}/{environment}` is an
unauthenticated, rate-limited endpoint. The seven-step pipeline handles
connection resolution, provider verification, payload hashing, deduplication,
raw payload storage, and state advancement.

- Duplicates are idempotent.
- Conflicting payloads are recorded as `DISAGREEMENT`.
- Amount/currency mismatches against the attempt are recorded as
  `DISAGREEMENT`.
- The event status vocabulary is: `RECEIVED`, `PROCESSED`, `DEDUPLICATED`,
  `REJECTED`, `UNPROCESSABLE`, `DISAGREEMENT`.

## Database migration

`alembic/versions/e4f5a6b7c8d9_add_v3_payment_tables.py` adds six tables:

| Table | Purpose |
| --- | --- |
| `payment_connections` | Provider connection with sealed credentials |
| `payment_connection_audit` | Append-only lifecycle audit trail |
| `payment_intents` | Collection request with idempotency guard |
| `payment_attempts` | Individual STK Push calls, sequentially numbered |
| `provider_transactions` | Provider response tracking for status queries |
| `payment_events` | Append-only inbound callback inbox |

Key constraints include:

- `UNIQUE (chama_id, provider_code, environment)` on connections.
- `CHECK amount > 0` and `CHECK currency = UPPER(currency)` on intents.
- `CHECK attempt_number > 0` on attempts.
- `CHECK completed_at IS NULL OR status IN ('SUCCEEDED', 'FAILED')` on
  attempts (completed_at only set for terminal statuses).
- `UNIQUE (payment_intent_id, attempt_number)` on attempts.
- `UNIQUE (connection_id, client_reference)` on attempts (prevents duplicate
  provider calls).
- `UNIQUE (connection_id, provider_event_id) WHERE provider_event_id IS NOT
  NULL` on events (deduplication index).

SQLite upgrade was verified on a scratch database; `alembic check` reports no
drift. PostgreSQL trigger and concurrency paths are covered by CI.

## Test coverage

| Test file | Count | Scope |
| --- | --- | --- |
| `test_provider_adapters.py` | 53 | Adapter contract tests with MockTransport |
| `test_credential_cipher.py` | 15 | AES-GCM round-trip, key rotation, tampering |
| `test_payment_connections.py` | 22 | Connection lifecycle, auth, validation |
| `test_payment_intents.py` | 16 | Intent creation, initiation, retry, timeout |
| `test_payment_webhooks.py` | 11 | Callback inbox, dedup, disagreement, binding |

All 224 non-concurrency tests pass on SQLite. PostgreSQL concurrency tests
are run by CI.

## Not implemented

- Jenga Daraja live provider integration tests (requires test credentials
  and sandbox accounts).
- Payment confirmations connected to the ledger (blocked by OQ-012/OQ-013).
- Loan, repayment, and payout flows (blocked by OQ-015..OQ-020).
- Bank reconciliation, notifications, background workers.
- React, React Native, USSD.