# ADR-011: Ledger Immutability and Corrections

## Status

Approved

## Decision

The financial ledger is **immutable and append-only**:

- A `ledger_transaction` and its `ledger_entries` cannot be updated or
  physically deleted.
- The application exposes no update or delete path for ledger records.
- A correction is recorded by posting a **compensating transaction**: a new
  transaction whose entries move the same amounts on the opposite side.

A compensating transaction:

- has `reverses_transaction_id` set to the original transaction it corrects,
- swaps the debit/credit side of every entry of the original transaction,
- is itself a normal, immutable transaction.

A transaction that already reverses another transaction cannot be reversed
again. A transaction that already has a reversal may not be reversed a second
time.

## Reason

This mirrors the approved V1 rule "Confirmed financial records cannot be
silently deleted" and extends it to the ledger. Immutable, balanced history
preserves the ability to prove how every balance came to be. Corrections add
new history instead of rewriting existing history.

## Consequences

- Corrections are visible in the transaction history as their own
  transactions, always referencing the original.
- The service rejects an attempt to reverse a reversal, and rejects a second
  reversal of the same transaction. A partial unique index
  (`uq_ledger_transactions_reversal`) enforces this at the database level.
- Database-level triggers (`trg_ledger_transactions_no_update`,
  `trg_ledger_transactions_no_delete`, `trg_ledger_entries_no_update`,
  `trg_ledger_entries_no_delete`) block UPDATE and DELETE on both
  `ledger_transactions` and `ledger_entries`. This makes the tables truly
  append-only at the database level, not just by application convention.
- The self-referencing reversal foreign key is composite
  `(chama_id, reverses_transaction_id) → (chama_id, id)`, preventing
  cross-Chama reversal references at the database level.
- The `updated_at` column has been removed from `ledger_transactions` and
  `ledger_entries` since these tables are immutable. `ledger_accounts` retains
  `updated_at` because accounts may be edited.

## Open questions affecting corrections

- The specific compensating rules for business events (for example whether a
  confirmed contribution later reverses as cash-in/cash-out entries) are
  business rules recorded in `OPEN_QUESTIONS.md` (OQ-013).