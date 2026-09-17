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

V1 (Chama Foundation) is implemented. V2 (Financial Core) is in progress:
the immutable double-entry ledger foundation, financial transaction history,
and V2 ledger hardening (composite FKs, append-only DB triggers, CHECK
constraints, cursor pagination, idempotency conflict handling) are
implemented. V3 (Payment Architecture) is implemented: provider-port
boundary, Jenga and Daraja adapters, payment connection lifecycle, payment
intent/attempt state machines, and a deduplicated webhook inbox.
All 235 automated tests pass; native PostgreSQL concurrency and trigger
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

API docs are available at `/docs`. Run the test suite with `pytest`.
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
- V3 payment architecture: provider-port boundary (ADR-016), payment
  connection lifecycle (ADR-017), webhook inbox and event deduplication
  (ADR-018), AES-GCM sealed credentials, Jenga and Daraja adapter contract
  tests (MockTransport), payment intent/attempt state machines with retry
  and timeout handling
- Observability: single-line JSON structured logs with `X-Request-ID`
  correlation ids echoed on responses, Prometheus `/metrics` endpoint,
  general per-IP API rate limiting beyond auth
- Operation: production runbook (`docs/12_PRODUCTION_RUNBOOK.md`),
  `Dockerfile` + Docker Compose app service, split runtime/dev dependency
  files with a pinned lockfile

### Not implemented (V2+, blocked or deferred)

- Loans, loan repayments, payouts (blocked by open questions)
- Contribution-to-ledger posting (blocked by open questions)
- Ledger-backed balances/reports
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
```

The application will refuse to start if `CHAMACORE_DEBUG` is false and
the JWT secret is still the local-development default.

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
