# Architecture

## Style

ChamaCore is a modular monolith: one FastAPI application and one primary
database. Modules are logically separated and may be extracted later if a
measured need arises, but they are not separately deployed services.

Do not rewrite the database layer, ORM, or framework. Do not replace the
ledger with mutable balances.

## Layers

```text
API
↓
Pydantic schemas
↓
Application services
↓
Repositories
↓
SQLAlchemy models
↓
Database
```

## Current structure

```text
app/
├── main.py                  # app factory, docs/metrics gating, security headers
├── core/                    # config, security, logging, metrics, rate limiting, errors
├── db/                      # sessions, bootstrap, ledger/audit guards
├── models/                  # identity, Chama, membership, ledger, payment, loan,
│                            # repayment, payout, registration-fee, audit models
├── providers/               # provider port, HTTP, Daraja/Jenga adapters, registry
├── schemas/                 # Pydantic input/output schemas
├── repositories/            # database access by domain
├── services/                # business workflows by domain
└── api/
    ├── deps.py              # authentication and rate-limit dependencies
    └── v1/                  # auth, Chama, membership, roles, fees, contributions,
                             # shares, ledger, loans, payouts, audit, payments,
                             # webhooks, and C2B routers

tests/
alembic/
scripts/                     # Daraja sandbox bootstrap and C2B registration helpers
```

## Rules

- Endpoints handle HTTP concerns; schemas validate input/output.
- Services contain business operations; repositories contain database access.
- SQLAlchemy models are not returned directly from endpoints.
- Authorization runs before returning Chama-scoped data.
- Business logic depends on the payment provider port, not a provider directly
  (`app/providers/base.py`, ADR-016).
- Financial workflows post through the trusted ledger service. The ledger is
  the source of truth for balances and corrections.

## Payment architecture

V3 payment providers are adapters behind an internal interface:

```text
Payment Service
  ↓
Provider Port (app/providers/base.py)
  ├── DarajaAdapter      ← registered provider (sandbox and production)
  └── JengaAdapter       ← code retained, not registered since 2026-09-17
```

Payments use payment connections (sealed credentials and controlled lifecycle,
ADR-017), payment intents, payment attempts, provider transactions, and a
deduplicated callback inbox (ADR-018). The system user performs C2B and STK
ledger settlement (ADR-019).

## Implemented financial modules

- Registration-fee payment and reversal (ADR-022).
- Loan application, eligibility, approval, disbursement, repayment, and
  repayment reversal (ADR-020).
- Payout request, approval, processing, completion, failure, and reversal
  (ADR-021).
- Append-only business audit events for defined sensitive actions (ADR-023).

These features remain in the modular monolith and preserve the API → schema →
service → repository → model layering. Money effects post through the trusted
ledger service; none of the modules maintains a competing balance.

## Remaining boundaries

- Financial reports beyond ledger history, account balances, and account
  entries remain undefined pending D-07.
- Notifications and bank reconciliation are not implemented; their scope is
  pending ratified decisions D-09 and D-10.
- Do not let route handlers become business-logic containers when extending
  features (scale report §19).
- Do not bypass the ledger to create parallel accounting (scale report §4).
