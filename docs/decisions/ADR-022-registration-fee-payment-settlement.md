# ADR-022: Registration-Fee Payment Settlement on the Ledger

## Status

Approved 2026-09-23 (resolves OQ-014; decision D-05 from
`OPEN_QUESTIONS.md`).

Implemented 2026-09-23: `app/services/registration_fee.py` (`pay`,
`reverse_payment`, `list_payments`), `app/models/registration_fee_payment.py`,
repos, schemas, API router `app/api/v1/registration_fees.py`, migration
`9a8b7c6d5e4f`, and `tests/test_registration_fee_settlement.py`.

## Context

V1 registration fees exist only as OWED or WAIVED rows (ADR-003); there is
no payment flow and no ledger treatment. `reports/latestreport.md` requires
registration-fee ledger settlement (completion-spec Phase 4, scale-report
step 4). Decision D-05 was recorded in `OPEN_QUESTIONS.md` and ratified by
the product owner.

## Decision

### Status

The `RegistrationFeeStatus` enum gains `PAID`. A fee is OWED when created
(ADR-003), WAIVED or PAID by explicit action, and OWED again only after its
payment is reversed (see below). Waiving a PAID fee is an invalid state.

### Payment recording

Recording a fee payment requires a `CHAIRPERSON` or `TREASURER` role (the
same roles that record contributions) and:

- creates a confirmed `registration_fee_payments` row (the financial
  artifact);
- marks the fee `PAID`; and
- posts one balanced ledger transaction, idempotent by
  `REGISTRATION_FEE_PAYMENT:<payment_id>`:

```text
Debit  1000 Cash (ASSET)
Credit 4000 Registration Fees (REVENUE)
```

The database enforces one confirmed payment per fee with a partial unique
index on `registration_fee_payments(fee_id)` where
`status = 'CONFIRMED'`, so a duplicate payment attempt can never create a
second financial effect. Money received as fee payment uses the same
accounting flow whether it arrives as cash or through a payment provider —
the posting service is the single entry point (spec §16: "cash and
electronic payment use the same accounting flow").

Paying an already-`PAID` fee is an idempotent no-op: the fee is returned and
no ledger row or payment row is created.

### Reversal

Reversing a `PAID` fee payment (a correction) requires `CHAIRPERSON` and:

- marks the payment row `REVERSED` (freeing the partial-unique slot);
- posts the standard compensating ledger reversal (ADR-011) referencing the
  fee payment posting; and
- sets the fee back to `OWED`, so the obligation is truthfully reinstated
  and can be settled again with a fresh payment row and ledger source id.

The ledger transaction for the original payment is never mutated.

### Waived fees and history

Waiving an OWED fee posts nothing — the decision exempts waived fees from
financial entries. No backfill migration runs over historical fees: existing
OWED/WAIVED rows are left untouched (D-05).

## Consequences

- Registration-fee money now flows through the immutable ledger exactly once
  per payment, with corrected payments restored to OWED instead of erasing
  history.
- OQ-014 is resolved; the scale-report "Registration-fee accounting" step
  and completion-spec Phase 4 are unblocked.
- ADR-003 remains authoritative for fee creation; this ADR only extends the
  lifecycle with PAID and payment/reversal actions.