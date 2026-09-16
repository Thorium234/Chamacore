# ADR-014: Contribution Posting to the Ledger (PROPOSED, BLOCKED)

## Status

Proposed — blocked on open questions

## Context

V1 confirms a contribution by changing its status to `CONFIRMED` and creating
a share record. V2 adds the ledger as the financial source of truth. When a
contribution is confirmed, the approved V2 model should post it to the
ledger. This ADR records the intended shape of that posting and why it cannot
be implemented yet.

## Proposed decision

When a contribution transitions from `PENDING` to `CONFIRMED`, the financial
action during confirmation posts one balanced ledger transaction derived from
the contribution.

When a `CONFIRMED` contribution transitions to `REVERSED`, the financial
action posts a compensating ledger transaction per ADR-011.

A contribution must never create more than one posting (the ledger
`source_type`/`source_id` uniqueness in ADR-012 is the backstop).

## Why it is blocked

The actual accounts to be debited and credited, and how they are derived,
are business rules that are not yet approved:

- OQ-012 — how a Chama's chart of accounts is created and maintained.
- OQ-013 — which accounts a confirmed contribution posts to (for example
  which asset account receives the cash, and which equity/revenue account is
  credited).

Until OQ-012 and OQ-013 are decided, the contribution-confirmation service
must not write to the ledger, because inventing the account mapping would
invent a business rule.

## Consequences

- The ledger migration, posting service, and ledger read endpoint are
  delivered in this increment; connections from confirmed contributions are
  not.
- No V1 behavior changes: confirmation and reversal of contributions continue
  to work exactly as in V1.
- This ADR becomes approved and step 4 of the V2 implementation order
  (connect confirmed contributions to the ledger) starts only after OQ-012
  and OQ-013 are answered.