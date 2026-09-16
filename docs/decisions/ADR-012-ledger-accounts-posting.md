# ADR-012: Ledger Accounts and Posting Rules

## Status

Approved

## Decision

### Ledger accounts

Every Chama has its own chart of accounts stored in `ledger_accounts`.

An account has:

- `chama_id` (accounts are Chama-scoped),
- `code` — unique within the Chama (`UNIQUE (chama_id, code)`),
- `name`,
- `account_type` — one of the standard five types:
  `ASSET`, `LIABILITY`, `EQUITY`, `REVENUE`, `EXPENSE`,
- a normal balance side derived from its type using standard accounting
  convention:

  - `ASSET` → debit
  - `EXPENSE` → debit
  - `LIABILITY` → credit
  - `EQUITY` → credit
  - `REVENUE` → credit

The default set of accounts a new Chama should receive, and how accounts are
created and maintained, is an open question (OQ-012). This increment delivers
the account table and the posting machinery; it does not seed a chart of
accounts.

### Posting rules

A financial transaction is accepted only when:

1. It contains at least one entry with `debit > 0` and at least one entry
   with `credit > 0`.
2. `sum(debit)` is exactly equal to `sum(credit)`.
3. Every entry references an account that exists in the transaction's Chama.
4. Every entry carries either a positive debit or a positive credit, never
   both and never neither.
5. Amounts are non-negative and quantized to two decimal places.

Posting to the ledger is **server-side and trusted**: the ledger can only be
written through `LedgerService.post_transaction`, which is invoked by an
approved business posting rule. There is no public API that accepts arbitrary
ledger entries.

### Idempotency

`source_type` and `source_id` identify the business event that produced a
transaction and are unique (`UNIQUE (source_type, source_id)`).

Posting a transaction whose `(source_type, source_id)` already exists is
treated as an **idempotent retry**: the existing transaction is returned and
no new rows are created. This makes retries after transient failures safe.

## Reason

Standard double-entry accounting requires balanced transactions and a defined
chart of accounts. Enforcing account existence, side rules, and balance in
the posting service prevents structuring bugs and gives database constraints
a clean surface. Source-reference uniqueness gives durable idempotency
without inventing a separate idempotency-key mechanism.

## Consequences

- Accounts must exist before any posting can reference them.
- Unbalanced, zero, or cross-chama postings are rejected with a domain error
  and no partial write. Cross-chama references are also blocked at the
  database level by composite foreign keys on `ledger_entries`
  (`(chama_id, account_id)` and `(chama_id, transaction_id)`).
- Account `account_type` is constrained to the five standard types
  (`ASSET`, `LIABILITY`, `EQUITY`, `REVENUE`, `EXPENSE`) by a database
  CHECK constraint. Account `code` and `name` must be non-empty (CHECK
  constraint).
- Posting the same business event twice is safe and returns the same
  transaction. Conflicting idempotent retries (different amounts, accounts,
  or description) raise `ConflictError`.
- The composition of the initial chart of accounts remains an open question
  (OQ-012) and must be answered before business events (for example confirmed
  contributions) are connected to the ledger (ADR-014).