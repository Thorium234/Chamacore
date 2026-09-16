# ADR-010: Financial Ledger and Financial Transactions

## Status

Approved

## Decision

ChamaCore introduces a financial ledger as the single source of truth for
approved financial activity. The ledger is a **double-entry** bookkeeping
system.

A **financial transaction** is a single, balanced, immutable accounting event
that:

- belongs to exactly one Chama (`chama_id`),
- groups one or more `ledger_entries`,
- has total debits exactly equal to total credits,
- references the source record that caused it (`source_type`, `source_id`),
- records the user who triggered it (`posted_by_user_id`),
- is never updated or deleted after creation.

A **ledger entry** is one side of a financial transaction:

- belongs to exactly one ledger transaction,
- references exactly one ledger account,
- carries either a `debit` amount or a `credit` amount (never both, never
  neither),
- uses `NUMERIC(18, 2)`.

The ledger is stored in three tables:

- `ledger_accounts` — the chart of accounts for a Chama (ADR-011),
- `ledger_transactions` — the financial transaction history,
- `ledger_entries` — the debit/credit lines of each transaction.

## Reason

A chama's financial activity (contributions, later loans and payouts) must be
recorded in a way that is provably balanced, attributable, and historical.
Double-entry bookkeeping is the standard accounting model and supports
auditing and reconciliation without inventing a proprietary format. Recording
a transaction's `source_type`/`source_id` preserves traceability to the
business event that created it.

## Consequences

- A financial transaction must balance before it is persisted; unbalanced
  posts are rejected by the service.
- A financial transaction can only be created through the trusted posting
  service (no public endpoint writes to the ledger).
- Ledger queries are Chama-scoped and require active membership
  authorization (ADR-013).
- Contributions, loans, and payouts will post to the ledger only through
  their approved posting rules (ADR-014, future ADRs).
- The schema is chama-scoped: no global transactions exist across Chamas.