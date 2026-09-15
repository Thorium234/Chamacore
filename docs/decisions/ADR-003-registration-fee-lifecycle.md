# ADR-003: Registration Fee Lifecycle

## Status

Approved

## Decision

When a Chama is created, its `registration_fee_amount` field stores the
current registration fee.

When a membership is created, the Chama's current `registration_fee_amount`
is copied into the membership's `registration_fees` row with status `OWED`.

Later changes to the Chama's registration fee do not alter existing fee rows.

Registration fee statuses are `OWED` or `WAIVED`. Payment recording is
deferred to V2 payment architecture.

A registration fee row may never be physically deleted.

## Reason

The approved business rule is that confirmed financial records cannot be
silently deleted. Copying the fee preserves a historical snapshot of the
amount at the time of membership creation.

## Consequences

- The Chama model must include a `registration_fee_amount` field.
- A registration fee row is created automatically at membership creation.
- Existing fee rows are immutable in amount (only status may change).
- Payment linkage is out of V1 scope.
