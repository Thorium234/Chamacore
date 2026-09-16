# V1 Database Specification

## Status

Implemented. Initial migration applied on SQLite for development.

## Strategy

- Development: SQLite
- Production: PostgreSQL
- ORM: SQLAlchemy 2.x
- Migrations: Alembic

## V1 tables

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

## General rules

- Use internal UUID primary keys.
- Every table has `created_at`.
- Mutable records have `updated_at`.
- Enforce foreign keys.
- Use `NUMERIC` for money.
- Reject negative amounts.
- Use controlled status values.
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
- Membership numbers are allocated transactionally.
- Membership numbers are unique within a Chama.
- Contributions reference memberships.
- Shares reference memberships and follow the approved formula.

## Membership number

The membership number belongs to `memberships`, not `members`.

Recommended constraint:

```sql
UNIQUE (chama_id, membership_number)
```

Never use:

```sql
SELECT COUNT(*) + 1
```

Use a transactional sequence or counter mechanism.

## Scope rule

V1 is complete. V2 ledger tables (`ledger_accounts`, `ledger_transactions`,
`ledger_entries`) are implemented with hardening (composite foreign keys,
append-only triggers, CHECK constraints, cursor pagination); see
`docs/10_V2_FINANCIAL_CORE.md` and ADR-010..ADR-015. Do not create payment,
bank, loan, loan-repayment, payout, webhook, or reconciliation tables until
their approved V2/V3 design allows it.