# V2 Implementation Report — Ledger Foundation

## Report metadata

- Repository: https://github.com/Thorium234/Chamacore
- Branch: `main`
- Date: 2026-09-16
- V2 current version per `docs/08_ROADMAP.md`

## What was built

The first V2 increment — the immutable double-entry ledger foundation and
financial transaction history:

### Design and decisions

- `docs/10_V2_FINANCIAL_CORE.md` — V2 financial core design (defines the
  ledger model, posting rules, precision, authorization, audit; explicitly
  marks loan/payout/contribution-posting rules unresolved).
- ADR-010 — ledger and financial transactions (double-entry, chama-scoped,
  source-referenced).
- ADR-011 — ledger immutability and compensating-entry corrections.
- ADR-012 — ledger accounts and posting rules (account types, balance/side
  rules, server-side trusted posting, source-reference idempotency).
- ADR-013 — ledger precision (`Decimal`/`NUMERIC(18,2)`, `ROUND_HALF_UP`),
  authorization, and audit.
- ADR-014 — contribution-to-ledger posting (Proposed; blocked by OQ-012/
  OQ-013).
- `docs/decisions/OPEN_QUESTIONS.md` — V2 open questions OQ-012..OQ-020.

### Implementation

- Three new tables (migration `c7d8e9f0a1b2_add_v2_ledger_tables.py`):
  - `ledger_accounts` (chama-scoped, `UNIQUE(chama_id, code)`, typed
    ASSET/LIABILITY/EQUITY/REVENUE/EXPENSE),
  - `ledger_transactions` (chama-scoped, actor, source reference with
    `UNIQUE(source_type, source_id)`, optional `reverses_transaction_id`),
  - `ledger_entries` (balance lines with non-negative and single-side CHECK
    constraints).
- `LedgerAccountType` enum.
- `LedgerService` with:
  - `post_transaction` — validates balance, sides, non-negativity, account
    existence in the Chama; idempotent retry returns the existing
    transaction;
  - `reverse_transaction` — posts a compensating transaction with swapped
    sides and a reversal reference; rejects reversing reversals and double
    reversals;
  - `list_by_chama` — active-membership authorization plus chama scoping.
- `GET /api/v1/chamas/{chama_id}/ledger` — financial transaction history
  endpoint (any active member).
- No public ledger write endpoints (posting is server-side only).

### Tests

`tests/test_ledger.py`, 15 tests:

- valid balanced posting,
- GET endpoint returns history with account and amount fields,
- unbalanced post rejected (no partial write),
- zero-amount and double-sided entries rejected,
- negative amounts rejected,
- account from another Chama rejected,
- unknown account rejected,
- idempotent retry returns the same transaction,
- compensating reversal with swapped sides and reversal reference,
- double reversal rejected,
- reversal of a reversal rejected,
- reads require an active membership (403 for strangers),
- chama-scoped reads,
- unauthenticated reads rejected (401),
- multiple source transactions recorded independently.

## Verification

```text
81 passed, 1 warning            (66 V1 + 15 V2 ledger)
python -m compileall -q app alembic tests scripts   -> passed
alembic upgrade head (fresh SQLite)                 -> passed (all 3 migrations)
alembic check                                       -> "No new upgrade operations detected."
alembic upgrade head (development chamacore.db)     -> applied c7d8e9f0a1b2
```

PostgreSQL was not runnable in this environment (no Docker); the V2 migration
is dialect-neutral (`sa.Uuid`, `VARCHAR` enums, portable CHECK constraints)
and the existing CI PostgreSQL jobs will exercise it on main.

## What remains blocked

- **Connecting confirmed contributions to the ledger** — blocked by OQ-012
  (chart of accounts) and OQ-013 (contribution posting accounts). ADR-014 is
  proposed, not approved.
- **Registration-fee payments on the ledger** — blocked by OQ-014.
- **Loans and loan repayments** — blocked by OQ-015..OQ-018 (eligibility,
  principal limits, interest/service charges, repayment schedules, late
  payments and defaults).
- **Payouts** — blocked by OQ-019/OQ-020 (eligibility, approval).

## No-guessing compliance

No unresolved business rule was guessed. Every rule that needed a decision is
either:

- an approved technical/accounting decision recorded in an ADR
  (ADR-010..ADR-013), or
- an open question recorded in `docs/decisions/OPEN_QUESTIONS.md` with the
  blocked work explicitly named (`OQ-012..OQ-020`).

V1 behavior is unchanged: all 66 V1 tests pass; the V1 migration sequence is
preserved; Authorization and Decimal/NUMERIC rules are met.