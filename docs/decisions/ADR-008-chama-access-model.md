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
- A user may create one Chama only. A linked member joins additional Chamas
  through membership registration by a Chama executive.
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

## Addendum 2026-09-15 (P0): One User per Member

A Member identity may be claimed by only one User account. This is enforced
at the database with `UNIQUE (users.member_id)` and in the linking service
(a second account claiming an already-claimed member returns `409 Conflict`).

This prevents two separate accounts from acting as the same person and
inheriting the same Chama leadership permissions.

## Addendum 2026-10-08: Founding eligibility for registered members

A newly registered account is linked to a Member before it owns a Chama. It
may therefore create its first Chama while that Member has no Memberships.
Once the linked Member belongs to any Chama, the backend rejects creation with
`409 Conflict`, irrespective of a different `member` object supplied by the
client. The frontend hides creation controls for that account.

A person who wants to found another Chama must use a separate account with a
phone number and government ID that are both unregistered, as required by
ADR-007. Existing members join other Chamas through executive membership
registration.
