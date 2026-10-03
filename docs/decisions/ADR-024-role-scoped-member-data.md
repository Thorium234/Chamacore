# ADR-024: Role-Scoped Member Financial Data

## Status

Approved — 2026-10-04

## Decision

- `CHAIRPERSON`, `TREASURER`, and `SECRETARY` may view group-wide membership,
  contribution, share, loan, payout, payment-intent, registration-fee, and
  ledger data in their Chama.
- Other active members may view their own membership and financial records
  only. A request naming another member's record is rejected with 403; an
  unfiltered collection read is scoped to the caller's membership.
- Members may download their own statement. Executives may request an
  individual member statement or a Chama-wide statement.
- `PLATFORM_ADMIN` sees aggregate platform overview data on the dashboard.
  Chama-scoped records still require an active membership and that membership's
  Chama role; the global platform role does not grant access to member records.
- An account already linked to a member cannot create a second Chama. The
  existing member joins other Chamas through executive membership registration.

## Reason

Members should not see other members' identity or financial details. Frontend
route hiding alone is not authorization, so the backend enforces these scopes
for direct API requests as well.

## Consequences

- Collection and membership-specific services must authorize their scope before
  returning records.
- The frontend shows members their own activity and redirects them away from
  executive management and group-ledger pages.
- The backend API contract and frontend API map must describe the same scope.
