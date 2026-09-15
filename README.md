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

V1 (Chama Foundation) is implemented. All 59 automated tests pass.

### Quick start

```bash
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
pytest
```

API docs are available at `/docs`.

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
- 59 automated tests

### Not implemented (V2+)

- Loans, loan repayments, payouts
- Ledger
- Payments, webhooks, payment providers
- Bank reconciliation
- Notifications
- React, React Native, USSD
- Background workers, microservices

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
