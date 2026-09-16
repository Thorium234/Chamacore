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
  reversal of the same transaction.
- Database-level protection (triggers) is not added in this increment;
  immutability is enforced by the posting service and by the absence of any
  repository update/delete methods. Trigger enforcement is a candidate for
  production hardening.

## Open questions affecting corrections

- The specific compensating rules for business events (for example whether a
  confirmed contribution later reverses as cash-in/cash-out entries) are
  business rules recorded in `OPEN_QUESTIONS.md` (OQ-013).