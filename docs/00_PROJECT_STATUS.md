# ChamaCore Project Status

## Status date

2026-09-16

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

V2 (Financial Core) has started. The immutable double-entry ledger
foundation and financial transaction history are implemented (ADR-010..015).
V2 hardening has been applied: composite FKs, append-only DB triggers, CHECK
constraints, cursor pagination, and idempotency conflict handling.
Loans, repayments, and payouts are blocked by open questions
(OQ-015..OQ-020).

## Currently executable

```text
alembic upgrade head
uvicorn app.main:app --reload
pytest
```

All 109 tests pass. Swagger docs are available at `/docs`.

## Implemented

- Application package structure (`app/`)
- Configuration via Pydantic settings
- SQLAlchemy 2.x models (10 V1 tables + 3 V2 ledger tables)
- Database sessions
- Alembic migrations (initial V1 schema, V1 unique constraints, V2 ledger)
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
- Tests (auth, chamas, memberships, roles, registration fees,
  contributions, membership-number concurrency, identity-claim uniqueness,
  constraint backstop, JWT config, health, ledger posting/idempotency/
  reversal/authorization/db-enforcement/concurrency)
- PostgreSQL test target (Docker Compose + CI workflow)
- Approved decisions recorded in ADRs and `docs/decisions/`

## Not implemented (out of scope / blocked)

- Loans, loan repayments, payouts (blocked by OQ-015..OQ-020)
- Connecting confirmed contributions to the ledger (blocked by OQ-012/OQ-013)
- Registration-fee payments on the ledger (blocked by OQ-014)
- Frontend
- Payment integrations
- Reconciliation
- Reports
- Notifications
- USSD

## Current milestone

V2: Financial Core. In progress — ledger foundation and V2 hardening
delivered; loans, repayments, and payouts await decisions.

Future versions (V3+ in `docs/08_ROADMAP.md`) describe direction only and
must not be implemented now.

## Official status statement

> V1 implemented and hardened (66 tests). V2 Financial Core started: ledger
> foundation, financial transaction history, and V2 ledger hardening
> implemented (109 tests total).
```

Reports: `reports/03_V2LedgerReviewReport.md` (independent review findings)
and `reports/04_V2LedgerHardening.md` (evidence that findings were
addressed).