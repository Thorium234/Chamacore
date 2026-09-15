# ADR-008: Chama Access Model

## Status

Approved

## Decision

When a user creates a Chama, the system:

1. Creates a `Member` record for the authenticated user (using the provided
   member details: first name, last name, phone number, government ID).
2. Links the `User` to the `Member` via `user.member_id`.
3. Creates a `Membership` with server-side membership number.
4. Assigns `CHAIRPERSON` and `MEMBER` roles to the membership.

Authorization for any Chama-scoped query requires the authenticated user to
be linked to a `Member` who holds an active `Membership` in that Chama.

## Reason

This mirrors the real-world chama pattern where the founder chairs the
group. It satisfies the approved rule "Verify authorization on every
Chama-scoped query" without guessing at role-based access beyond what is
already decided in ADR-006.

## Consequences

- Chama creation requires member details in the request body.
- A user may only create a Chama once (the first time); subsequent Chama
  creations by a user who is already linked to a member require using the
  existing member link (or the endpoint allows creation without re-creating
  the member).
- Authorization is membership-based: no membership = no access.

## Addendum 2026-09-15: Identity claim endpoint

A user who is not yet linked to a `Member` may claim their identity via
`POST /api/v1/auth/me/member-link` by supplying the matching `phone_number`
and `government_id` of an existing `Member` record (e.g. a member added by
a Chama administrator). The claim succeeds only when both fields match the
same member.

- A user already linked to a member cannot claim again (conflict).
- No matching member returns not found.
- This is how a user other than the Chama creator becomes able to act within
  a Chama after being added as a member by an administrator.
