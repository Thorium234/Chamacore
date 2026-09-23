# ADR-021: Payout Lifecycle, Approval, and Ledger Integration

## Status

Approved 2026-09-23 (resolves OQ-019, OQ-020; decision D-04 and the payout
half of D-06 from `OPEN_QUESTIONS.md`).

Implemented 2026-09-23: `app/services/payout.py`, `app/models/payout.py`,
repos, schemas, API router `app/api/v1/payouts.py`, migration
`9a8b7c6d5e4f`, and `tests/test_payouts.py`.

## Context

`reports/latestreport.md` (CHAMACORE_BACKEND_COMPLETION_SPEC) requires a
complete payout lifecycle: payout requests, approvals, processing,
completion with a financial record, failure paths, and compensating
reversals. No payout eligibility or approval rules were previously
recorded, so decision D-04 was recorded in `OPEN_QUESTIONS.md` and ratified
by the product owner.

## Decision

### Lifecycle

```text
REQUESTED
    ↓
APPROVED
    ↓
PROCESSING
    ↓
COMPLETED
```

Failure paths: REQUESTED→REJECTED and PROCESSING→FAILED. A completed payout
may later be corrected with REQUESTED→...→COMPLETED→REVERSED (compensating
reversal). The state machine is enforced in the service layer and the enum
in the database; no arbitrary transitions are allowed.

### Eligibility and amount (D-04)

Any `ACTIVE` member may request a payout when:

- `amount > 0`;
- `amount <=` the member's outstanding share value, defined as their share
  value (sum of `ACTIVE` share units times the share unit price) minus the
  sum of their already-`COMPLETED` (non-reversed) payouts;
- `amount <=` the Chama's available cash, derived from the ledger `1000` Cash
  account balance (computed from posted entries on demand, never stored).

The share-value cap means a member can never receive more than the equity
they have contributed, and the per-member cumulative check runs over
completed payouts only.

### Approval and execution

- Approval: `CHAIRPERSON`. The requester can never approve their own payout
  (`actor` must differ from the requester user).
- Processing (money is being moved) and completion (money has left the
  Chama): `CHAIRPERSON` or `TREASURER`.
- Failure (PROCESSING→FAILED): `CHAIRPERSON` or `TREASURER`, with a
  mandatory `failure_reason`. A failed payout posts no ledger entry.
- Completions and reversals are idempotent: retrying a completion returns
  the completed payout and never double-posts.

### Ledger integration (D-06)

Completion posts, atomically with the `COMPLETED` status change:

```text
Debit  3000 Share Capital (EQUITY)
Credit 1000 Cash (ASSET)
```

idempotency key `PAYOUT_COMPLETION:<payout_id>`, so "completed payout has a
financial record" and "ledger record without completed payout" are both
impossible.

Reversal of a `COMPLETED` payout posts the standard compensating reversal
(ADR-011) referencing the completion posting and marks the payout
`REVERSED`. Completed payouts are never deleted and never mutated.

### Cross-Chama and duplicate protection

Every query and mutation is scoped by `chama_id`, and the composite foreign
keys on the `payouts` table make a payout's Chama ownership a database
constraint (`(chama_id, membership_id)` references memberships). Duplicate
approval of an already-`APPROVED` payout and duplicate completion of an
already-`COMPLETED` payout are rejected as invalid state rather than
creating new financial effects.

## Consequences

- Payouts now exist with strong controls (approval, ledger posting,
  reversal) wired to the immutable ledger.
- OQ-019 and OQ-020 are resolved; the scale-report "Payouts" step and
  completion-spec Phase 3 are unblocked.
- Payout reporting fields (D-07) remain blocked only on the report
  definition decision.
- The `3000` Share Capital account is the payout funding pool; the ledger
  remains the sole authority over cash availability.