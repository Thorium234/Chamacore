# ADR-013: Ledger Precision, Authorization, and Audit

## Status

Approved

## Decision

### Precision and rounding

- All ledger money amounts use `Decimal` in Python and `NUMERIC(18, 2)` in
  the database.
- Floating-point numbers are never used for money.
- Amounts are quantized to two decimal places with `ROUND_HALF_UP`.
- Balance checks compare quantized `Decimal` values exactly.
- Aggregate values returned from the ledger (for example account totals) are
  computed over `NUMERIC` columns so precision survives aggregation.

### Authorization

- **Reads** — the financial transaction history endpoint of a Chama is
  available to any active member of that Chama, matching the V1 convention
  for contributions and shares. Chama-scoping is enforced on every query.
- **Writes** — posting is triggered by an approved business action that has
  already authorized the actor. `LedgerService.post_transaction` additionally
  requires the actor to be an active member of the Chama (defense in depth).
- Raw posting endpoints are not exposed.

### Audit

Every ledger transaction records:

- the user who triggered the posting (`posted_by_user_id`),
- when it was posted (`created_at`),
- the source record it came from (`source_type`, `source_id`),
- and, for corrections, the transaction it reverses
  (`reverses_transaction_id`).

This is the financial audit trail for postings. A general-purpose audit event
table for all sensitive V2 actions is planned separately and is not part of
this increment.

## Reason

The V1 money rules already require `Decimal`/`NUMERIC`. The ledger inherits
them and adds explicit rounding so balances always agree. Chama-scoped
authorization is the established V1 pattern, and recording the actor on every
posting satisfies audit requirements for the ledger without inventing a new
permission model.

## Consequences

- Ledger responses never expose passwords, secrets, or cross-Chama data.
- A user without an active membership in a Chama cannot read its ledger.
- Every posting is attributable to a user and a source record.
- An entry is only writable by the posting service, never by an endpoint.