# ADR-014: Contribution Posting to the Ledger

## Status

Approved 2026-09-22 (resolves OQ-013)

## Context

V1 confirms a contribution by changing its status to `CONFIRMED` and creating
a share record. V2 adds the ledger as the financial source of truth. When a
contribution is confirmed, it is posted to the ledger.

## Decision

When a contribution transitions from `PENDING` to `CONFIRMED`, the financial
action during confirmation posts one balanced ledger transaction derived from
the contribution:

- debit `1000` Cash (ASSET)
- credit `3000` Share Capital (EQUITY)
- for the full contribution amount

The posting is idempotent: the ledger `source_type`/`source_id` uniqueness in
ADR-012 is the backstop, using source type `CONTRIBUTION_CONFIRMATION` and
source id `<contribution_id>`. A contribution can never create more than one
posting, and every re-confirmation of an already-posted contribution is a
no-op for the ledger.

When a `CONFIRMED` contribution transitions to `REVERSED`, the financial
action posts a compensating ledger transaction per ADR-011 (reversal reversing
the contribution confirmation posting). Reversal is only possible if the
posting exists.

System-triggered postings (settlement of manually-confirmed contributions,
see ADR-019) are performed as the seeded system user
(`system@chamacore.invalid`), which cannot log in. `post_transaction` skips
`authorize_chama_access` for non-user postings only; user-initiated postings
are still authorization-checked per ADR-013.

## Consequences

- Confirmation and reversal of contributions write to the ledger exactly once.
- The chart of accounts seeded at Chama creation (OQ-012 / ADR-019) supplies
  the `1000`/`3000` accounts used here.
- V1 behavior is unchanged except for the ledger write happening alongside
  status change and share creation.
- Authorization, precision, and audit rules in ADR-013 apply to the new
  postings.