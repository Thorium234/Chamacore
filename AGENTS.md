# ChamaCore Agent Instructions

## Before coding

Read the numbered documents in `docs/` and any accepted ADRs in
`docs/decisions/` before changing code. For the current development direction
also read `reports/CHAMACORE_SCALE_ENGINEERING_REPORT.md`.

## Current scope

The governance version is `docs/08_ROADMAP.md`; the governing development
brief is `reports/CHAMACORE_SCALE_ENGINEERING_REPORT.md`. Its order of work:

1. Repository consistency (docs must agree with reality) — done `2026-09-23`
2. Deferred-test inventory (every skip has a reason and an activation path)
   — done `2026-09-23`
3. Financial domain decisions (registration fees, loans, repayments, payouts)
4. Registration-fee accounting
5. Loans
6. Loan repayments
7. Payouts
8. Financial reporting
9. Business audit trail
10. Security hardening
11. Integration testing
12. Performance measurement

### COMPLETED (do not re-implement)

- V1 Chama Foundation: users, chamas, members, memberships, roles,
  registration fees, contributions, shares, authentication, authorization,
  migrations, tests
- V2 Financial Core that is not decision-blocked (ADR-010..ADR-015, and the
  approved parts of ADR-019):
  - Immutable double-entry ledger, enforcement hardening, cursor pagination
  - Chart-of-accounts seeding per Chama (`1000` Cash, `3000` Share Capital,
    `4000` Registration Fees)
  - Contribution confirmation/reversal ledger posting (ADR-014)
  - C2B/STK settlement posting (ADR-019, resolves OQ-012/OQ-013/OQ-021)
  - Read-only ledger account balances and per-account entries
- V3 Payment Architecture (ADR-016..ADR-018): provider port with the Daraja
  adapter active (Jenga retained but unregistered), payment connection
  lifecycle, intent/attempt state machines, deduplicated webhook inbox
- Production readiness (developer brief `reports/ChamaCore_Developer_
  Implementation_Brief.md`): short access tokens with rotating refresh flow,
  docs/metrics gating, security headers, system-user login guard

### NEXT WORK (blocked unless a decision is recorded)

Steps 4–9 of the scale report are all decision-blocked. Do not guess them:

- Registration-fee payments on the ledger — blocked by OQ-014
- Loans — blocked by OQ-015..OQ-018
- Loan repayments — blocked by OQ-015..OQ-018
- Payouts — blocked by OQ-019 / OQ-020
- Financial reporting beyond the existing ledger balances/entries — blocked on
  report definitions
- Business audit events — blocked on which sensitive actions to record

### DEFERRED

- Jenga as an active provider (adapter code and contract tests retained,
  unregistered since 2026-09-17; 27 Jenga tests skipped — see
  `docs/13_TEST_INVENTORY.md`)
- Live provider sandbox integration tests (requires test credentials)
- Notifications, bank reconciliation, USSD, frontend, background workers

### OUT OF SCOPE

- Microservices, Kubernetes, Kafka, distributed databases, event sourcing /
  CQRS as replacements, Redis everywhere, a rewrite of the ledger, payment
  flows, ORM, or framework
- Moonlighting: do not add unrelated providers (KCB BUNI, NCBA) without a
  documented requirement

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
must not directly depend on a payment provider. Preserve the modular
monolith; do not break module boundaries during feature work.

## Financial and security rules

- Use `Decimal` and database `NUMERIC` for money.
- Never use floating-point numbers for money.
- The ledger is the authoritative financial record. Business modules must not
  maintain competing financial truths.
- Never silently delete confirmed financial records; corrections are
  compensating transactions.
- Every operation that can create a financial effect must be idempotent and
  protected by the database (`UNIQUE` references), not just application
  memory.
- Use controlled status values and database constraints.
- Use transactions for related writes.
- Use migrations for every schema change.
- Never store plaintext passwords, provider credentials, or commit secrets.
- Never trust client-supplied ownership, roles, balances, or Chama IDs.
- Verify authorization on every Chama-scoped query.
- Do not expose sensitive identity fields (e.g. `government_id`) through
  ordinary responses.

## Testing and completion

Every feature requires tests, especially authorization, duplicate records,
concurrent membership registration, invalid amounts, status transitions,
rollback, and historical-record protection.

A feature is complete only when its approved rule, migration, API contract,
tests, and documentation all agree (scale report §29).

Never delete failing tests and never mark tests as skipped merely to make CI
green. Every deferred test must have a reason and an activation path recorded
in `docs/13_TEST_INVENTORY.md`.

Implement only the current version in `docs/08_ROADMAP.md`.