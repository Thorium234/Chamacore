# ADR-009: Contribution Statuses and Corrections

## Status

Approved

## Decision

### Statuses

Contributions use the following controlled statuses:

- `PENDING`: recorded but not yet confirmed.
- `CONFIRMED`: confirmed and immutable in amount.
- `REVERSED`: a correction; the original amount is preserved and the
  reversal is recorded.

### Recording and confirmation

- Only a user with `CHAIRPERSON` or `TREASURER` role in the Chama may
  record a contribution.
- Only a user with `CHAIRPERSON` role may confirm a `PENDING` contribution.

### Corrections

- A `CONFIRMED` contribution cannot be edited or deleted.
- A correction is recorded by creating a reversal: the contribution status
  is changed to `REVERSED` and an optional note explains the reason.
- Only the `CHAIRPERSON` may reverse a contribution.
- A reversed contribution retains its original amount and period.

### Duplicate rule

A membership may have at most one non-reversed contribution per calendar
period. A second contribution in the same period is rejected regardless of
amount.

### No physical deletion

Confirmed or reversed contribution records may never be physically deleted.
Status is changed; the row is preserved.

## Reason

This satisfies the approved rule "Confirmed financial records cannot be
silently deleted" while providing a practical correction mechanism for V1.

## Consequences

- Contributions have a three-state status enum: `PENDING`, `CONFIRMED`,
  `REVERSED`.
- A `note` field on the contribution allows an explanation for reversals.
- The confirmation and reversal endpoints require role authorization checks.
- Share records tied to a reversed contribution are not physically deleted
  but marked with a reference to the reversal.
