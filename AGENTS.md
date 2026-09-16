# ChamaCore Agent Instructions

## Before coding

Read the numbered documents in `docs/` and any accepted ADRs in
`docs/decisions/` before changing code.

## Current scope

V1 (Chama Foundation) is complete. Only V2 (Financial Core) may be
implemented now:

- Users
- Chamas
- Members
- Memberships
- Roles
- Registration fees
- Contributions
- Shares
- Authentication and authorization
- Database migrations
- Automated tests
- V2 financial ledger (ADR-010..ADR-013)
- Financial transaction history
- Loans and loan repayments (only after the loan open questions are answered)
- Payouts (only after the payout open questions are answered)

Do not implement yet:

- Connecting confirmed contributions to the ledger (blocked by OQ-012/OQ-013
  in `docs/decisions/OPEN_QUESTIONS.md` unless an approved decision allows it)
- Payments or webhooks
- Jenga, Daraja, KCB BUNI, or NCBA
- Bank reconciliation
- Notifications
- React or React Native
- USSD
- Background workers unless explicitly required by an approved V2 decision
- Microservices

V2 loans, repayments, and payouts remain blocked until the corresponding
open questions are answered. Do not guess those rules.

## No guessing

Never invent business rules, status values, permission rules, share formulas,
database relationships, API formats, or deletion behavior.

If a decision is missing:

1. Do not silently choose an implementation.
2. Record it in `docs/decisions/OPEN_QUESTIONS.md`.
3. Explain which work is blocked.
4. Ask for a decision.

## Architecture

Use:

```text
API
↓
Pydantic schema
↓
Service
↓
Repository
↓
SQLAlchemy model
↓
Database
```

Do not return SQLAlchemy models directly from API endpoints. Business logic
must not directly depend on a payment provider.

## Financial and security rules

- Use `Decimal` and database `NUMERIC` for money.
- Never use floating-point numbers for money.
- Never silently delete confirmed financial records.
- Use controlled status values and database constraints.
- Use transactions for related writes.
- Use migrations for every schema change.
- Never store plaintext passwords or commit secrets.
- Never trust client-supplied ownership, roles, balances, or Chama IDs.
- Verify authorization on every Chama-scoped query.

## Testing and completion

Every feature requires tests, especially authorization, duplicate records,
concurrent membership registration, invalid amounts, status transitions,
rollback, and historical-record protection.

A feature is complete only when its approved rule, migration, API contract,
tests, and documentation all agree.

Implement only the current version in `docs/08_ROADMAP.md`.