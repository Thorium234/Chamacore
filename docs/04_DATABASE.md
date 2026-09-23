# Database Specification

## Status

Implemented. V1, V2 (Financial Core), V3 (Payments) tables, and the
`refresh_tokens` table are migrated. Initial V1 migration applied on SQLite
for development; PostgreSQL is the production integration target.

## Strategy

- Development: SQLite
- Production: PostgreSQL
- ORM: SQLAlchemy 2.x
- Migrations: Alembic (the migration history is part of the system; never edit
  a database manually and let migrations catch up)

## Tables

### V1 — Chama Foundation

- `users`
- `chamas`
- `members`
- `memberships`
- `roles`
- `membership_roles`
- `registration_fees`
- `contributions`
- `shares`
- `membership_sequences`

### V2 — Financial Core (ADR-010..ADR-015)

- `ledger_accounts`
- `ledger_transactions`
- `ledger_entries`

### Authentication sessions

- `refresh_tokens` (only SHA-256 digests of refresh tokens; single-use,
  revocable) — migration `a1f0c3e5b7d9`

### V3 — Payments (ADR-016..ADR-018)

- `payment_connections`
- `payment_connection_audit`
- `payment_intents`
- `payment_attempts`
- `provider_transactions`
- `payment_events`

## General rules

- Use internal UUID primary keys.
- Every table has `created_at`.
- Mutable records have `updated_at` (ledger transactions and entries do not —
  they are append-only).
- Enforce foreign keys.
- Use `NUMERIC` for money.
- Reject negative amounts.
- Use controlled status values with CHECK constraints.
- Do not physically delete important financial records.

## Required constraints

- `users.email` is unique.
- `users.member_id` is unique (one User per Member).
- `members.phone_number` is unique.
- `members.government_id` is unique.
- A membership references an existing member and Chama.
- `registration_fees.membership_id` is unique (one fee per membership).
- `shares.contribution_id` is unique (one share per confirmed contribution).
- A person cannot have duplicate membership in one Chama.
- A role assignment cannot be duplicated.
- Membership numbers are allocated transactionally and unique within a Chama
  (`UNIQUE (chama_id, membership_number)`); never `COUNT(*) + 1`.
- Contributions reference memberships.
- Shares reference memberships and follow the approved formula.

### Ledger constraints (ADR-010..ADR-015)

- `UNIQUE (chama_id, code)` on `ledger_accounts`; `account_type` CHECK in
  `ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE`; non-blank code/name CHECKs.
- `UNIQUE (source_type, source_id)` on `ledger_transactions` (idempotency).
- `UNIQUE (chama_id, id)` on all ledger tables (ownership hardening).
- Composite foreign keys `(chama_id, transaction_id)` and `(chama_id,
  account_id)` on `ledger_entries`; composite self-referencing reversal FK.
- Partial unique index on `reverses_transaction_id` WHERE NOT NULL (one
  reversal per transaction).
- Append-only: SQLite and PostgreSQL `BEFORE UPDATE/DELETE` triggers raise on
  `ledger_transactions` and `ledger_entries`.
- PostgreSQL deferred triggers verify balanced transactions and entries at
  commit time.

### Payment constraints (ADR-016..ADR-018)

- `UNIQUE (chama_id, provider_code, environment)` on `payment_connections`.
- `CHECK amount > 0` and currency-format CHECK on intents.
- `UNIQUE (payment_intent_id, attempt_number)` and `UNIQUE (connection_id,
  client_reference)` on attempts (prevents duplicate provider calls).
- `UNIQUE (connection_id, provider_event_id) WHERE provider_event_id IS NOT
  NULL` on events (deduplication index).
- Attempts: `completed_at` set only for terminal statuses
  (`SUCCEEDED`, `FAILED`).

## Scope rule

V1, the non-decision-blocked V2 Financial Core, V3 Payments, and the refresh
token tables are implemented and migrated. Do not create loan,
loan-repayment, payout, audit-event, or report tables (and do not extend the
chart of accounts) until their approved ADR design exists. The V3 payment
tables and C2B/STK settlement exist; loans, repayments, payouts, and audit
remain blocked by OQ-014..OQ-020 and open design decisions.

## Migration history

- `68ce987eb072` — initial V1 schema
- `a1b2c3d4e5f6` — unique constraints (users, registration_fees, shares)
- `c7d8e9f0a1b2` — V2 ledger tables
- `d1e2f3a4b5c6` — V2 ledger hardening (ownership, immutability, balance,
  account types)
- `e4f5a6b7c8d9` — V3 payment tables
- `f2b4d6a8e0c1` — seed system user and default chart of accounts (OQ-012,
  ADR-019)
- `a1f0c3e5b7d9` — refresh tokens table (production readiness 3.1)