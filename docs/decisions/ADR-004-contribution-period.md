# ADR-004: Contribution Period

## Status

Approved

## Decision

A contribution period is a calendar month represented as a string in
`YYYY-MM` format, for example `2026-09`.

A contribution references exactly one period string. The period is supplied
by the client and validated as a valid `YYYY-MM` string.

## Reason

Calendar-month periods are the standard for Kenyan savings chamas. A single
string column is simple and sufficient. No additional period-configuration
table is required in V1.

## Consequences

- The contributions table stores period as `VARCHAR(7)`.
- Validation requires the value to match `YYYY-MM`.
- No two contributions in the same period may be duplicates for the same
  membership (business rule pending).
