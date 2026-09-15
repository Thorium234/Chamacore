# ADR-002: Separate Member from Membership

## Status

Accepted

## Decision

`Member` represents a person. `Membership` represents that person's
participation in one specific Chama.

Chama-specific financial records reference `Membership`.

## Reason

One person may belong to multiple Chamas, with different roles, identifiers,
statuses, and financial histories in each one.

## Consequence

Membership numbers belong to `memberships` and are unique within a Chama.