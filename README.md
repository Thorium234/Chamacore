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

ChamaCore is currently in the V1 foundation stage.

The repository currently contains a minimal FastAPI application and product,
domain, architecture, and database documentation. The following are not
implemented yet:

- Database models or migrations
- Authentication or authorization
- Chama, member, membership, contribution, or share APIs
- Payment-provider integrations
- Frontend applications
- Automated tests

The only current executable endpoint is:

```text
GET /
```

It currently returns:

```json
{"message": "Hello World"}
```

## Current implementation target

V1 is:

```text
Chama → Member → Membership → Roles → Registration Fees → Contributions → Shares
```

Do not implement loans, payments, bank integrations, React, mobile, USSD,
or microservices until V1 is complete and approved.

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

## Planned technology

- Python
- FastAPI
- SQLAlchemy 2.x
- Alembic
- SQLite for development
- PostgreSQL for production
- Pydantic
- pytest

## No-guessing rule

If a business rule is missing, contradictory, or marked `OPEN`, do not guess.
Record the issue in `docs/decisions/OPEN_QUESTIONS.md` and stop the blocked
implementation.