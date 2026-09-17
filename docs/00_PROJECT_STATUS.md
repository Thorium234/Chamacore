# ChamaCore Project Status

## Status date

2026-09-17

## Status note (17 Sep 2026)

Following the independent code-review reports (`reports/Overall_ChamaCore_
Code_Review_Report.md`, `reports/Afternoon_ChamaCore_Code_Review_Report.md`),
the following hardening/observability work landed on `main`:

- Auth and general API rate limiting (in-process, per client IP)
- Reversal idempotency ordering fix in the ledger posting path
- Payment status-query retryable-flag fix (permanent vs transient failures)
- Single-line JSON structured logs with `X-Request-ID` correlation ids
- Prometheus `/metrics` endpoint (HTTP counters + latency histograms)
- Production runbook, Dockerfile, Docker Compose app service, dependency
  split with a pinned lockfile

## Final verdict

V1 (Chama Foundation) is implemented and its automated tests pass.

The repository is now a working backend for:

- Users and authentication
- Chamas
- Members and memberships
- Roles
- Registration fees
- Contributions and shares
- Authorization on every Chama-scoped query
- Database migrations and automated tests
- V1 hardening: identity-claim uniqueness, DB-level constraint backstops,
  government-ID masking, JWT secret fail-closed, health/readiness endpoints

V2 (Financial Core) is implemented. The immutable double-entry ledger
foundation, financial transaction history, and V2 ledger hardening
(composite FKs, append-only DB triggers, CHECK constraints, cursor
pagination, idempotency conflict handling) are delivered (ADR-010..015).

V3 (Payment Architecture) is implemented (ADR-016..018): a provider-port
boundary with the Daraja adapter (Jenga code retained but unregistered since
17 Sep 2026 — Daraja is the only active provider), sealed payment connections
with a chairperson-controlled lifecycle, payment intent/attempt state
machines, and a deduplicated, append-only webhook inbox.

C2B (manual Paybill money-in) plumbing per the 17 Sep M-Pesa validation
report: strict callback schemas, `/payments/c2b/validate|confirm/{connection_id}`
endpoints bound by per-connection token with `TransID` idempotency, a
chairperson-only Register-URL activation endpoint, and fail-closed behaviour —
every validation is rejected (`ResultCode 1`) and confirmations never touch
the ledger until the BillRefNumber rule is approved (OQ-021; gated by
OQ-012/OQ-013).

Loans, repayments, and payouts are blocked by open questions
(OQ-015..OQ-020), as is contribution-to-ledger posting (OQ-012/OQ-013).

## Currently executable

```text
alembic upgrade head
uvicorn app.main:app --reload
pytest
```

Of 259 tests, 232 pass on SQLite and 27 Jenga adapter contract tests are
deferred (skipped); native PostgreSQL concurrency and trigger paths run in
CI. Swagger docs are available at `/docs`.

## Implemented

- Application package structure (`app/`)
- Configuration via Pydantic settings
- SQLAlchemy 2.x models (10 V1 tables + 3 V2 ledger tables + 6 V3 payment
  tables)
- Database sessions
- Alembic migrations (initial V1 schema, V1 unique constraints, V2 ledger,
  V2 ledger hardening, V3 payment tables)
- SQLite for development; PostgreSQL support for production
- Authentication (register, token, me, member-link)
- Authorization (membership-based, verified per Chama-scoped query)
- Chama, member, membership, role, registration-fee, contribution, and
  share endpoints
- Server-side transactional membership numbers
- V2 immutable double-entry ledger: accounts, transactions, entries
- V2 ledger posting service with balance/side/non-negativity validation,
  quantization-before-validation, and source-reference idempotency
- V2 financial transaction history endpoint with cursor pagination
- V2 compensating-entry reversal for the ledger
- V2 hardening: composite FKs, append-only DB triggers, CHECK constraints,
  partial unique index for reversals, idempotency conflict handling,
  reversal metadata validation (ADR-015)
- V3 provider port and provider registry (ADR-016)
- V3 Daraja adapter (STK Push, status query, callback parsing) with mocked
  HTTP contract tests; Jenga adapter code retained but unregistered since
  17 Sep 2026 (one-line rollback); Daraja OAuth tokens cached per consumer
  key (~50 minutes)
- V3 payment connection lifecycle with AES-256-GCM sealed credentials,
  chairperson authorization, validation, and audit trail (ADR-017)
- V3 payment intent/attempt state machines with retry, timeout, and
  idempotency handling
- V3 webhook inbox with database-backed deduplication and disagreement
  detection (ADR-018)
- C2B (manual Paybill) plumbing (report 17 Sep 2026): strict `C2BCallbackBody`
  schema, `POST /payments/c2b/validate/{connection_id}` and
  `POST /payments/c2b/confirm/{connection_id}` endpoints (token-bound,
  `TransID`-prefixed event ids, payload-hash deduplication/disagreement),
  Database-backed receipt storage in the webhook inbox, and a
  chairperson-only `register-c2b-urls` activation endpoint that points
  Safaricom at the connections' Validation/Confirmation URLs. Validation is
  fail-closed (`ResultCode 1`); confirmation is acknowledged and stored but
  posts nothing to the ledger (OQ-021/OQ-012/OQ-013).
- Structured logging: single-line JSON with `X-Request-ID` correlation ids
  echoed on request/response (middleware + `app/core/logging.py`)
- Prometheus-exposition `/metrics` endpoint with HTTP request counters and
  latency histograms, bounded route-template labels (`app/core/metrics.py`)
- General per-IP API rate limiting beyond auth, plus the existing
  auth/payment/webhook limits (all in-process)
- Daraja-only provider focus (17 Sep 2026): Jenga is no longer registered,
  so no new Jenga connection can be created; the Jenga adapter code and
  `JENGA` enum value are retained for a one-line rollback. Sandbox
  credential workflow documented in `.env.example`.
- Daraja OAuth token cache (~50 min TTL, per consumer key, per environment)
  so repeated STK Push/status-query calls skip the token round-trip
- Optional sandbox bootstrap script `scripts/create_daraja_connection.py`
  (stdlib-only) that reads `DARAJA_*` from env and creates/validates the
  connection through the API
- One-time C2B activation script `scripts/register_daraja_c2b_urls.py`
  (stdlib-only API client; chairperson login) that calls the connection's
  register-URL endpoint so the server binds the C2B callbacks
- Production runbook (`docs/12_PRODUCTION_RUNBOOK.md`), application
  `Dockerfile`, Docker Compose app service, and runtime/dev dependency split
  with `requirements.lock.txt`
- Tests (auth, chamas, memberships, roles, registration fees,
  contributions, membership-number concurrency, identity-claim uniqueness,
  constraint backstop, JWT config, health, ledger posting/idempotency/
  reversal/authorization/db-enforcement/concurrency, credential cipher,
  payment connections, payment intents, payment webhooks, provider adapters,
  C2B callbacks and register-URL activation)
- PostgreSQL test target (Docker Compose + CI workflow)
- Approved decisions recorded in ADRs and `docs/decisions/`

## Not implemented (out of scope / blocked)

- Loans, loan repayments, payouts (blocked by OQ-015..OQ-020)
- Connecting confirmed contributions to the ledger (blocked by OQ-012/OQ-013)
- C2B validation acceptance and C2B confirmation-to-ledger credit (blocked by
  OQ-021, gated by OQ-012/OQ-013) — callbacks are received, stored, and
  acknowledged, but no money is credited
- Registration-fee payments on the ledger (blocked by OQ-014)
- Live Jenga/Daraja sandbox integration tests (requires live test accounts)
- Frontend
- Bank reconciliation
- Reports
- Notifications
- USSD

## Current milestone

V3: Payment Architecture is implemented (ADR-016..018). Contribution
confirmation, ledger posting, loans, repayments, and payouts await the
remaining V2 financial decisions (OQ-012..OQ-020).

## Official status statement

> V1 implemented and hardened (66 tests). V2 Financial Core implemented:
> ledger foundation, financial transaction history, and V2 ledger hardening
> (109 tests at that point). V3 Payment Architecture implemented:
> provider port (Jenga + Daraja), sealed payment connections, intent/attempt
> state machines, webhook inbox. 17 Sep hardening: auth + general API rate
> limits, ledger reversal idempotency, payment retryable-flag fix, JSON
> structured logs with correlation ids, Prometheus `/metrics` endpoint,
> production runbook, Docker Compose app service. 17 Sep finalization:
> Daraja is the only active provider (Jenga unregistered, code retained for
> one-line rollback), Daraja OAuth token cache, `.env.example`, a
> stdlib-only Daraja connection bootstrap script, and C2B manual-Paybill
> plumbing (fail-closed validation + idempotent confirmation storage,
> register-URL activation). Tests: 232 passed + 27 Jenga contract tests
> deferred (259 total).

Reports: `reports/03_V2LedgerReviewReport.md` (independent review findings),
`reports/04_V2LedgerHardening.md` (evidence that findings were addressed),
`reports/05_v3_payment_architecture.md` (V3 implementation evidence),
`reports/Overall_ChamaCore_Code_Review_Report.md` (17 Sep morning review),
`reports/Afternoon_ChamaCore_Code_Review_Report.md` (17 Sep afternoon
re-review whose remaining technical items are implemented above), and
`reports/ChamaCore_Finalization_Report.md` (17 Sep finalization review whose
implementable items — docs to HEAD, Daraja OAuth cache, seed script — are
implemented above).