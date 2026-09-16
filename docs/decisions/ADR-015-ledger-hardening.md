# ADR-015: Ledger Hardening — Database-Enforced Ownership, Immutability, and Constraints

## Status

Approved

## Decision

The V2 ledger review (reports/03_V2LedgerReviewReport.md) found that core
financial-safety rules were enforced only in the application layer and that
two ledger tables had been written as mutable. This ADR adopts the review's
findings and moves enforcement to the database level.

### V2-003 — Chama ownership enforced with composite foreign keys

`ledger_entries` gains a denormalized `chama_id`. Composite foreign keys
make cross-Chama references structurally impossible:

- `FK (chama_id, transaction_id) → ledger_transactions (chama_id, id)`
- `FK (chama_id, account_id) → ledger_accounts (chama_id, id)`
- `FK (chama_id, reverses_transaction_id) → ledger_transactions (chama_id, id)`

Both `ledger_transactions` and `ledger_accounts` gain
`UNIQUE (chama_id, id)` to serve as the composite FK targets.

### V2-004 — Ledger tables are truly append-only

- `update_at` is removed from `ledger_transactions` and `ledger_entries`
  (they are immutable records; `ledger_accounts` keeps `updated_at`).
- SQLite and PostgreSQL both receive guard triggers that raise on any
  `UPDATE` or `DELETE` of a ledger transaction or entry:
  - `trg_ledger_transactions_no_update`
  - `trg_ledger_transactions_no_delete`
  - `trg_ledger_entries_no_update`
  - `trg_ledger_entries_no_delete`

### V2-005 — Balanced-transaction invariant (PostgreSQL; SQLite documented)

PostgreSQL receives deferred constraint triggers
(`trg_chama_core_ledger_transaction_balanced`,
`trg_chama_core_ledger_entries_balanced`) that verify at commit time that
every transaction has at least two entries and that total debits equal total
credits.

SQLite does not support deferrable constraint triggers; the invariant
remains application-enforced there. This is a documented, accepted
limitation (the application layer already rejects unbalanced transactions).

### V2-006 — Reversal rules enforced in the database

- A partial unique index `uq_ledger_transactions_reversal` on
  `reverses_transaction_id WHERE reverses_transaction_id IS NOT NULL`
  permits at most one reversal per original transaction.
- The service validates reversal metadata before any idempotency lookup: a
  transaction with `reverses_transaction_id` must use the approved reversal
  source type, the target must exist in the same Chama, must not itself be a
  reversal, and must not already have a reversal.

### V2-007 — Account type and non-blank CHECK constraints

- `ck_ledger_accounts_type`: `account_type IN ('ASSET', 'LIABILITY',
  'EQUITY', 'REVENUE', 'EXPENSE')`. The non-native `Enum` emits no CHECK
  constraint on SQLite or PostgreSQL, so an explicit CHECK is required.
- `ck_ledger_accounts_non_blank`:
  `length(trim(code)) > 0 AND length(trim(name)) > 0`.

### V2-001 — Quantization before validation

`LedgerService.post_transaction` normalizes every line amount first
(`ROUND_HALF_UP` to two decimal places), then validates. This means every
entry sees the same rounds the user would see; a sub-cent pair that rounds
both sides to zero is rejected, and halves always round up — on both sides —
so balances still reconcile.

### V2-002 — Idempotent retry conflicts are rejected

Reposting an existing `(source_type, source_id)` returns the existing
transaction only when the normalized payload matches (Chama, description,
reversal reference, and ledger lines). A conflicting retry raises
`ConflictError`. This prevents silent payload drift on retries and a
cross-Chama source leak.

### V2-008 — Cursor pagination for history

`GET /chamas/{chama_id}/ledger` returns `LedgerHistoryOut` with
`items`, `next_cursor`, `has_more`, using keyset pagination on
`(created_at DESC, id DESC)`. The cursor is base64-encoded JSON.

## Reason

Independent review (reports/03) found the financial core was only
conventionally safe: a bug or future bypass in the service layer could
rewrite or delete ledger history, reference accounts from another Chama, or
double-reverse a transaction. The ledger is the source of truth for all V2
money movement; its safety rules must hold at the storage layer.

## Consequences

- SQLite and PostgreSQL schemas for the three ledger tables now encode
  ownership, immutability, and value constraints.
- The dev database was migrated to the new schema; `alembic check` reports
  no new upgrade operations.
- Tests cover DB-level enforcement on SQLite (cross-Chama entry/reversal,
  update/delete blocking, unsupported account type, blank code/name, second
  reversal) and application-level tightening on posting (quantization,
  idempotency conflicts, reversal metadata).
- PostgreSQL trigger paths are covered by CI (`test-postgres` and
  `concurrency-postgres` jobs).
- Naive offset pagination is removed. The ledger history API is
  cursor-based; this is a breaking change to the response contract.
- `alembic check` passes on SQLite after the hardening migration with no
  spurious enum diff.

## Open questions

Unchanged from ADR-014 and `OPEN_QUESTIONS.md`. In particular, connecting
confirmed contributions to the ledger (OQ-012/OQ-013) and all loan,
repayment, and payout rules (OQ-015..OQ-020) remain blocked.