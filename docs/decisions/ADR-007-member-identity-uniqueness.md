# ADR-007: Member Identity Uniqueness

## Status

Approved

## Decision

Both `phone_number` and `government_id` are globally unique on the `members`
table.

A UNIQUE constraint is applied to `members.phone_number` and
`members.government_id`.

During member creation, if either field already exists, the creation is
rejected with a conflict error.

## Reason

A member represents a real person. Duplicate identities undermine the
integrity of membership and financial records.

## Consequences

- The `members` table has unique indexes on `phone_number` and
  `government_id`.
- Duplicate phone or government ID returns an error at creation time.
- A person may still belong to multiple Chamas via separate memberships.
