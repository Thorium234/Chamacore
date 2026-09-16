# ChamaCore V3 Payment Architecture Report

## Verification metadata

- Repository: `https://github.com/Thorium234/Chamacore`
- Branch: `main`
- Mission prompt: `reports/05_version3_Payments.md`
- Baseline commit: `b74d822` (Harden V2 ledger per implementation review)
- V3 commit: see git log for the commit following this report
- Report date: 2026-09-16

## Verification environment

```text
SQLite:                    226 passed, 0 failed (dev, Windows)
  - V1/V2 regression:      107 passed (excluding 2 concurrency tests
                           collected separately)
  - V3 payment tests:      117 passed
  - Concurrency (SQLite):  2 passed
Dev DB migration (sqlite:///./chamacore.db): passed (d1e2f3a4b5c6 -> e4f5a6b7c8d9)
Fresh scratch DB:          upgrade empty -> head, downgrade -> V2 head,
                           re-upgrade -> head: passed (SQLite)
Alembic check after head migration: no new upgrade operations
compileall:                clean
PostgreSQL:                CI jobs (test-postgres, concurrency-postgres)
```

PostgreSQL cannot be exercised locally (no Docker); native PostgreSQL paths
are verified in CI only, as documented in `docs/10_V2_FINANCIAL_CORE.md`,
`docs/11_V3_PAYMENT_ARCHITECTURE.md`, and ADR-016..ADR-018. The baseline
PostgreSQL duplicate-trigger blocker is resolved: `create_ledger_guards`
(`app/db/ledger_guards.py`) is idempotent — triggers are dropped before being
created and functions use `CREATE OR REPLACE` — so the migration and the test
fixture can both install the guards against an already-migrated PostgreSQL
database without failing.

## Definition of done

| # | Requirement | Status |
| --- | --- | --- |
| 1 | PostgreSQL trigger-test setup defect fixed | RESOLVED (idempotent guards, `app/db/ledger_guards.py`, already in baseline) |
| 2 | V1 & V2 tests pass on SQLite | 107 passed (SQLite) |
| 3 | Payment-domain and provider-abstraction ADRs approved | ADR-016/017/018 written |
| 4 | Credential encryption and chairperson-only connection management implemented and tested | `payment_connection.py` + `credential_cipher.py`, 22 connection tests, 15 cipher tests |
| 5 | Jenga sandbox adapter and mocked contract tests | `JengaAdapter` + MockTransport contract tests |
| 6 | Payment intent and attempt state machines implemented | `payment_intent.py`, 16 intent tests |
| 7 | Idempotency and callback deduplication database-backed | 5 partial unique indexes + unique constraints, 11 webhook tests |
| 8 | No raw credentials in responses, logs, traces, errors | Verified by tests; `SecretStr`-style masking + redaction |
| 9 | No guessed contribution-to-ledger rules | Verified (no ledger writes from payment layer) |
| 10 | Daraja STK Push behind the same provider-neutral interface | `DarajaAdapter` implements `ProviderPort` |
| 11 | Migrations and `alembic check` pass | 6-table migration + clean autogenerate check |
| 12 | Report names every remaining provider limitation and unresolved rule | See "Limitations" below |

## What was built

### ADRs

- `docs/decisions/ADR-016-provider-port-adapters.md` — the `ProviderPort`
  contract, `JengaAdapter`, `DarajaAdapter`, the provider registry keyed by
  `(provider_code, environment)`, raw-body webhook handling, and credential
  sealing.
- `docs/decisions/ADR-017-payment-connection-lifecycle.md` — connection
  identity/uniqueness, statuses, chairperson authorization, credential
  handling, validation/rate limiting, deletion rules, audit trail.
- `docs/decisions/ADR-018-payment-webhook-inbox.md` — the unauthenticated
  rate-limited webhook endpoint, the seven-step processing pipeline,
  connection resolution, deduplication, and the event status vocabulary.

### Provider port and adapters

`app/providers/base.py` defines `ProviderPort`; the payment domain never
imports a concrete adapter. `app/providers/registry.py` provides a
`ProviderRegistry` and `build_default_registry()`.

- `JengaAdapter` (Finserve api-checkout STK Push): OAuth-style
  `/authentication/api/v3/authenticate/merchant`, STK Push
  `/api-checkout/mpesa-stk-push/v3.0/init`, status query by order reference,
  best-effort RSA PKCS1v15 SHA-256 `Signature` header when a
  `signing_private_key` is configured (otherwise omitted).
- `DarajaAdapter` (Safaricom Lipa Na M-Pesa): OAuth `/oauth/v1/generate`,
  `/mpesa/stkpush/v1/processrequest` with `base64(ShortCode+Passkey+EAT
  timestamp)` password, `/mpesa/stkpushquery/v1/query` keyed on
  `CheckoutRequestID`, whole-number KES amount enforcement.

Both adapters normalize Kenyan phone numbers to `2547XXXXXXXX`, isolate
sandbox vs production base URLs per instance, and expose the same
`PaymentAttemptResult` / `StatusQueryResult` / `ParsedCallback` shapes.

### Connection lifecycle

`app/services/payment_connection.py` implements ADR-017: create (seals
credentials with AES-256-GCM), list/get, replace (bumps credential version),
validate (rate-limited, adapter-backed), disable (idempotent), delete
(blocked when financial history exists). All mutations are chairperson-only;
reads and validation are open to any active member. The audit table is
append-only with `ON DELETE CASCADE` so a history-free connection can still
be deleted.

### Intent and attempt state machines

`app/services/payment_intent.py` implements the intent/attempt/prov ider-
transaction orchestration:

- Intents are idempotent by `(chama_id, idempotency_key)` with payload-hash
  matching; same key + different payload → `409`.
- `PENDING → PROCESSING → SUCCEEDED/FAILED`, terminal states closed.
- `initiate()` runs exactly one in-flight attempt; retries only after
  transient/retryable failures and inside the retry budget.
- `PERMANENT_FAILURE_CODES` prevents retrying known non-retryable provider
  errors.
- Provider timeouts and integration errors are captured as safe,
  non-secret errors; a timeout returns the same TIMEOUT attempt on re-initiate.
- Ambiguous attempts are resolved through the provider status query; a
  `provider_transactions` row tracks normalized + raw status for every
  attempt.

### Webhook inbox

`app/api/v1/payments_webhooks.py` exposes
`POST /api/v1/payments/webhooks/{provider_code}/{environment}` (raw body read
via `Request.body()`; rate-limited by provider+environment+client IP).
`app/services/payment_webhook.py` implements the ADR-018 pipeline:
size check → connection resolution (token-first, attempt-binding fallback) →
provider verification → payload hash → deduplication by
`(connection_id, provider_event_id)` with `DISAGREEMENT` on conflicting
payloads → raw payload storage → amount/currency-matched state transition.

### Migration

`alembic/versions/e4f5a6b7c8d9_add_v3_payment_tables.py` adds six tables
(`payment_connections`, `payment_connection_audit`, `payment_intents`,
`payment_attempts`, `provider_transactions`, `payment_events`) with unique
and CHECK constraints listed in the migration; `alembic check` reports no
drift. Feel free to downgrade `e4f5a6b7c8d9` on a scratch database: verified
round-trip.

## Test coverage added

| Test file | Count | Coverage |
| --- | --- | --- |
| `tests/test_provider_adapters.py` | 53 | Adapter contract tests with `httpx.MockTransport` (request paths, headers, bodies, response mapping, phone normalization, signature verification, error mapping, status normalization) |
| `tests/test_credential_cipher.py` | 15 | AES-GCM round-trip, plaintext-absence, nonce uniqueness, wrong-key/chama/connection failure, malformed blobs, key rotation |
| `tests/test_payment_connections.py` | 22 | Create (chair-only), secrets never exposed, duplicate `(chama, provider, env)`, cross-chama 403, validation transitions, rate limit 429, replace version bump, disable idempotency, delete-with-history 409, member reads |
| `tests/test_payment_intents.py` | 16 | Idempotent create, same-key conflicts, inactive membership, first-attempt initiation, post-success idempotency, ambiguous resolution, permanent vs retryable failure, timeout handling, cross-chama isolation |
| `tests/test_payment_webhooks.py` | 11 | Success processing, dedup, disagreement (payload/amount/currency), verification failure, token fallback, invalid token, unknown connection, failed callback leaves intent in `PROCESSING` |

Total new tests: 117. Full SQLite suite: 226 passed.

## Fixes made along the way

- `test_payment_webhooks` initially failed with `422 json_invalid` because
  `raw_payload: bytes = Body(...)` made FastAPI JSON-parse an
  `application/json` body. The endpoint now reads the raw body via
  `Request.body()`.
- `app/providers/jenga/adapter.py::decrypted_credentials` raised `KeyError`
  on the optional `signing_private_key` field; it now filters present keys.
- `app/providers/daraja/adapter.py::validate_credentials` propagated
  `ProviderIntegrationError` instead of returning an invalid result; it now
  converts auth failures to `valid=False` like the Jenga adapter.
- `app/models/payment_attempt.py` and the migration: `completed_at` CHECK
  constraint widened to allow `FAILED` attempts to be terminal.
- `app/models/payment_connection_audit.py` and the migration: audit FK is
  `ON DELETE CASCADE` so deleting a connection without financial history is
  not blocked by its own audit rows.
- `app/schemas/payment.py`: `PaymentAttemptOut` exposes `retryable`.
- `app/core/credential_cipher.py`: nonce generation moved to `os.urandom`
  (the runtime cryptography version has no `AESGCM.generate_nonce`).

## Limitations and unresolved business rules

### Provider limitations (each documented in the provider ADRs)

1. **Jenga IPN payload/signature contract is merchant-specific.** The exact
   canonical string for the STK Push `Signature` header must be confirmed
   with Jenga before go-live; when no `signing_private_key` is configured the
   header is omitted. Callback security relies on attempt binding, the secret
   per-connection callback token, HTTPS, amount matching, and deduplication.
2. **Daraja exposes no per-payload signature or hash.** Callback security
   relies on the same controls (attempt binding, callback token, HTTPS,
   amount matching, replay controls). This is a documented provider property,
   not an implementation gap.
3. **No live sandbox verification was run.** Both adapters are covered by
   mocked contract tests; real Jenga/Daraja sandbox integration requires live
   test accounts and is intentionally not part of the offline suite.

### Unresolved business rules (blocked, unchanged)

- Connecting confirmed contributions to the ledger remains blocked by
  OQ-012/OQ-013 (chart of accounts and contribution posting accounts).
- Registration-fee payment posting remains blocked by OQ-014.
- Loans, loan repayments, and payouts remain blocked by OQ-015..OQ-020.
- The `payment_intents.contribution_id` column exists but is never populated
  and no contribution-confirmation or ledger-posting transition is
  implemented; nothing in the payment layer can mark a contribution
  `CONFIRMED`.

## Operational notes

- **Timeouts:** provider HTTP timeout is configurable via
  `provider_http_timeout_seconds`; timeouts raise `ProviderTimeoutError`
  (safe) and leave the attempt re-initable.
- **Retryable vs non-retryable:** provider error codes in
  `PERMANENT_FAILURE_CODES` are never retried; everything else is retried up
  to the attempt limit.
- **Idempotency boundaries:** intent idempotency key (unique per Chama),
  client reference (unique per connection), provider request/event IDs
  (partial unique indexes), deduplicated webhook events.
- **Correlation:** intents, attempts, provider transactions, and events are
  linked by stable UUIDs; provider request/event IDs are stored for
  reconciliation.
- **Ambiguous-payment reconciliation:** an in-flight or ambiguous attempt is
  resolved by a provider status query; a callback with a `DISAGREEMENT` or an
  unresolved status remains visible for manual review via the event/attempt
  read endpoints.