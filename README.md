# ChamaCore

ChamaCore is a Kenyan Chama management platform.

The long-term system is intended to support:

- Chama management
- Members and memberships
- Roles and permissions
- Contributions
- Shares
- Loans and repayments
- Payouts
- Payments and reconciliation
- Financial records
- Reports and audit history

## Current status

V1 (Chama Foundation) and V2 (Financial Core) are implemented: the immutable
double-entry ledger, financial transaction history, V2 ledger hardening
(composite FKs, append-only DB triggers, CHECK constraints, cursor
pagination, idempotency conflict handling), chart-of-accounts seeding per
Chama, and contribution-to-ledger posting with compensating reversals
(ADR-014). V3 (Payment Architecture) is implemented: provider-port boundary,
Daraja adapter (Jenga code retained but not registered — Daraja is the only
active provider), sealed payment connection lifecycle, payment intent/attempt
state machines, C2B Paybill intake, STK/contribution settlement (ADR-019),
and a deduplicated webhook inbox. Production-readiness hardening is applied:
short-lived access tokens (120 minutes) with a rotating refresh-token flow,
interactive docs and the raw OpenAPI schema disabled in production, `/metrics`
protected by a shared token (404 otherwise), and minimal security headers in
production builds. Ledger account balances and per-account entries are exposed
read-only, always computed from posted entries. Of 307 automated tests, 280
pass and 27 are deferred (skipped); native PostgreSQL concurrency and trigger
paths are additionally run in CI.

### Quick start

```bash
python -m venv env
source env/bin/activate     # macOS/Linux; on Windows (PowerShell): env\Scripts\activate
pip install -r requirements.txt       # runtime; add requirements-dev.txt for tests
pip install -r requirements.lock.txt  # optional: reproducible locked environment
alembic upgrade head
uvicorn app.main:app --reload
```

API docs are available at `/docs` in debug builds (disabled in production).
Run the test suite with `pytest`.
Production operation is covered in `docs/12_PRODUCTION_RUNBOOK.md`.

### Implemented

- Users and authentication (register, token, me, claim member identity)
- Chamas (create, view, update, status)
- Members and memberships (create, view, update status)
- Roles (assign and remove leadership roles)
- Registration fees (view, waive)
- Contributions (record, confirm, reverse)
- Shares (created automatically on confirmation per ADR-005)
- Authorization on every Chama-scoped query
- Database migrations (Alembic)
- 66 automated tests (V1)
- V2 ledger foundation: immutable double-entry ledger, financial transaction
  history, trusted posting service with idempotency and compensating
  corrections (43 additional tests)
- V2 ledger hardening: composite Chama-ownership foreign keys, append-only
  triggers, account-type/non-blank CHECK constraints, one-reversal-per-
  transaction partial unique index, cursor pagination, quantization-before-
  validation, idempotency conflict handling
- V2 chart of accounts seeded per Chama (OQ-012 / ADR-019): `1000` Cash,
  `3000` Share Capital, `4000` Registration Fees; existing Chamas backfilled
  by migration `f2b4d6a8e0c1`
- V2 contribution-to-ledger posting (ADR-014, OQ-013): confirmation debits
  Cash / credits Share Capital idempotently; reversal posts a compensating
  reversal; system-triggered settlements run as the seeded system user
  (`system@chamacore.invalid`)
- V3 payment architecture: provider-port boundary (ADR-016), payment
  connection lifecycle (ADR-017), webhook inbox and event deduplication
  (ADR-018), AES-GCM sealed credentials, Jenga and Daraja adapter contract
  tests (MockTransport), payment intent/attempt state machines with retry
  and timeout handling. **Active provider: Daraja** (sandbox + production);
  the Jenga adapter code is retained but not registered. Daraja OAuth tokens
  are cached per consumer key (~50 minutes). Sandbox bootstrapping via
  `scripts/create_daraja_connection.py`; one-time C2B activation via
  `scripts/register_daraja_c2b_urls.py`.
- C2B (manual Paybill money-in, OQ-021 / ADR-019): strict callback schemas
  and `/payments/c2b/validate/{connection_id}` and
  `/payments/c2b/confirm/{connection_id}` endpoints with token binding,
  `TransID`-based idempotency and duplicate/disagreement detection, a
  chairperson-only register-URL activation endpoint, `BillRefNumber` =
  membership number resolved to an ACTIVE membership on an ACTIVE connection,
  and confirmation-to-contribution settlement with ledger posting.
- STK settlement (ADR-019): a succeeded payment intent settles its linked
  contribution as the system user, idempotently.
- Authentication hardening (production-readiness brief 3.1, 3.6): access
  tokens default to a 120-minute lifetime with `expires_in` in the token
  response, a rotating single-use refresh-token flow
  (`POST /api/v1/auth/refresh`), logout revocation
  (`POST /api/v1/auth/logout`), and the system posting account rejected at
  login. Migration `a1f0c3e5b7d9` adds the `refresh_tokens` table.
- Production API surface (brief 3.2, 3.3, 3.5): `/docs`, `/redoc`, and
  `/openapi.json` return 404 when `CHAMACORE_DEBUG=false`; `/metrics` requires
  `X-Metrics-Token` matching `CHAMACORE_METRICS_TOKEN` (404 if unset or wrong)
  in production; production builds send `X-Content-Type-Options`,
  `Referrer-Policy`, and `Strict-Transport-Security` as defense in depth.
- Ledger account balances and statements (brief 4.2): read-only
  `GET /chamas/{chama_id}/ledger/accounts` (signed balances always computed
  from posted entries) and
  `GET /chamas/{chama_id}/ledger/accounts/{account_id}/entries` with the same
  cursor pagination as transaction history, Chama-scoped authorization
  enforced on both.
- Observability: single-line JSON structured logs with `X-Request-ID`
  correlation ids echoed on responses, Prometheus `/metrics` endpoint,
  general per-IP API rate limiting beyond auth
- Operation: production runbook (`docs/12_PRODUCTION_RUNBOOK.md`),
  `Dockerfile` + Docker Compose app service, split runtime/dev dependency
  files with a pinned lockfile

### Not implemented (V2+, blocked or deferred)

- Registration-fee payments on the ledger (blocked by OQ-014)
- Loans, loan repayments, payouts (blocked by OQ-015..OQ-020)
- Aggregated reports/balances beyond the read-only ledger account balances
  and per-account entries
- Audit event table
- Bank reconciliation
- Notifications
- React, React Native, USSD
- Background workers, microservices

## Production configuration

For any deployed environment:

```bash
export CHAMACORE_DEBUG=false
export CHAMACORE_JWT_SECRET_KEY="<a-strong-random-secret>"
export CHAMACORE_DATABASE_URL="postgresql+psycopg://user:pass@host:5432/dbname"
export CHAMACORE_METRICS_TOKEN="<a-strong-random-secret>"
```

The application will refuse to start if `CHAMACORE_DEBUG` is false and
the JWT secret is still the local-development default. With
`CHAMACORE_DEBUG=false`, API docs are hidden and `/metrics` requires the
`X-Metrics-Token` header.

See `docs/12_PRODUCTION_RUNBOOK.md` for the full environment variable table,
migrations, secrets, backups, and monitoring guidance.

## Documentation source of truth

Before changing code, read:

1. `AGENTS.md`
2. `docs/00_PROJECT_STATUS.md`
3. `docs/01_PRODUCT_REQUIREMENTS.md`
4. `docs/02_DOMAIN_MODEL.md`
5. `docs/03_BUSINESS_RULES.md`
6. `docs/04_DATABASE.md`
7. `docs/05_ARCHITECTURE.md`
8. `docs/06_API_CONTRACT.md`
9. `docs/08_ROADMAP.md`
10. `docs/10_V2_FINANCIAL_CORE.md`
11. `docs/11_V3_PAYMENT_ARCHITECTURE.md`
12. `docs/12_PRODUCTION_RUNBOOK.md`
13. `docs/13_TEST_INVENTORY.md`

The governing development brief is `reports/CHAMACORE_SCALE_ENGINEERING_REPORT.md`.
Accepted decisions are in `docs/decisions/`.

## Technology

- Python
- FastAPI
- SQLAlchemy 2.x
- Alembic
- SQLite (development) / PostgreSQL (production)
- Pydantic
- pytest

## No-guessing rule

If a business rule is missing, contradictory, or marked `OPEN`, do not guess.
Record the issue in `docs/decisions/OPEN_QUESTIONS.md` and stop the blocked
implementation.
