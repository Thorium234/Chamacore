# Architecture

## Style

ChamaCore is a modular monolith: one FastAPI application and one primary
database. This is a deliberate, durable decision (scale report §18): the
modules below stay logically separate so future extraction is possible, but
they are not separately deployed services.

Do not rewrite the database layer, the ORM, or the framework. Do not replace
the ledger with mutable balances.

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
├── core/                    # config, security (JWT, refresh, hashing), logging, metrics,
│                            # callback token derivation, rate limiting, error mapping
├── db/                      # base, session, bootstrap (system user), ledger guards
├── models/                  # SQLAlchemy models (V1 + V2 ledger + V3 payment + refresh tokens)
├── providers/               # provider port (base.py) + HTTP, Daraja/Jenga adapters, registry
├── schemas/                 # Pydantic input/output schemas
├── repositories/
├── services/                # business operations (auth, chama, membership, contribution,
│                            # ledger, payment_connection, payment_intent, settlement, cipher)
└── api/
    ├── deps.py              # auth/rate-limit dependencies
    └── v1/                  # routers: auth, chamas, memberships, roles, contributions,
                             # shares, registration_fees, ledger, payments, webhooks, c2b

tests/
alembic/
scripts/                     # sandbox bootstrap + C2B registration helpers
```

## Rules

- Endpoints handle HTTP concerns.
- Schemas validate external input and output.
- Services contain business operations.
- Repositories contain database access.
- Models represent persistence.
- Authorization runs before returning Chama-scoped data.
- SQLAlchemy models are not returned directly from endpoints.
- Business logic must not depend on a payment provider directly; it depends on
  the provider port (`app/providers/base.py`, ADR-016).

## Payment architecture (implemented)

V3 payments are implemented (ADR-016..ADR-018). Providers are adapters behind
an internal interface; the rest of the system depends only on the port:

```text
Payment Service
  ↓                  ProviderRegistry
Provider Port (app/providers/base.py)
  ├── DarajaAdapter      ← only registered adapter (sandbox + production)
  └── JengaAdapter       ← code retained, not registered since 2026-09-17
```

Payments are layered as: payment connections (sealed credentials, lifecycle,
ADR-017) → payment intents (idempotent collection requests) → payment
attempts (single STK Push calls) → provider_transactions (response tracking)
→ payment_events (deduplicated inbound callback inbox, ADR-018). The system
user (`system@chamacore.invalid`) performs system-triggered ledger postings
(C2B confirmation and STK settlement, ADR-019).

## Observed boundaries

- Registration fees, loans, repayments, payouts, financial reports, and audit
  events do not yet exist as modules; they are decision-blocked (see
  `docs/08_ROADMAP.md`).
- Do not let route handlers become business-logic containers when adding
  features (scale report §19).
- Do not bypass the ledger to create parallel accounting (scale report §4).