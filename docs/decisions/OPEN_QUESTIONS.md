# Open Questions

These questions block implementation until answered.

## OQ-001: Registration fee lifecycle

What is the exact lifecycle of a registration fee?

Options:

1. Copy the fee from the Chama when membership is created.
2. Create it as an amount owed.
3. Record it only when manually paid.
4. Create an obligation and later link it to a payment.

Decision: `OPEN`

## OQ-002: Contribution period

What identifies a contribution period?

Options:

1. Calendar month such as `2026-09`.
2. A configured Chama period.
3. An arbitrary label.
4. A date range.

Decision: `OPEN`

## OQ-003: Share formula

How are shares calculated from contributions?

Decision: `OPEN`

## OQ-004: Role rules

Which roles may assign, remove, approve, or confirm records?

Decision: `OPEN`

## OQ-005: Identity uniqueness

Are phone numbers and government ID numbers globally unique?

Decision: `OPEN`

## Resolution rule

When a question is answered, create an ADR, update
`docs/03_BUSINESS_RULES.md`, and change the decision to `APPROVED`.