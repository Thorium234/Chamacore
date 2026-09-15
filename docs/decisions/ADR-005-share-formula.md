# ADR-005: Share Formula

## Status

Approved

## Decision

Each confirmed contribution creates one share record.

Share units are calculated as:

```
units = contribution_amount / SHARE_UNIT_PRICE
```

Where `SHARE_UNIT_PRICE` is a global constant defined in application
configuration, defaulting to KES 100. The result is stored as a `NUMERIC`
value (not a whole number; fractional shares are allowed).

Shares are created automatically when a contribution is confirmed.

A share record is linked to both the membership and the contribution.

## Reason

The formula ties each share record to a specific contribution, preserving
historical traceability. A single global unit price keeps the V1
implementation simple while remaining configurable.

## Consequences

- `SHARE_UNIT_PRICE` must be set in application configuration.
- Share records include `units` (NUMERIC) and a foreign key to the
  contribution.
- When a contribution is reversed, its associated share records are marked
  `REVERSED`, never physically deleted (reversal is a status change on both
  the contribution and its shares).
- Fractional units are permitted and stored as NUMERIC.
