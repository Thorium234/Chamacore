# V1 API Contract

## Status labels

- `PLANNED`: documented but not implemented
- `IMPLEMENTED`: implemented and tested
- `DEPRECATED`: no longer valid

## Root

### `GET /`

Status: `IMPLEMENTED`

Returns `{"message": "Hello World"}`. Will become a health endpoint later.

## Health and Readiness

### `GET /health`

Status: `IMPLEMENTED`

Returns `{"status": "ok"}`. No database check.

### `GET /ready`

Status: `IMPLEMENTED`

Returns `{"status": "ready"}`. Verifies database connectivity.

## Authentication

### `POST /api/v1/auth/register`

Status: `IMPLEMENTED`

Registers a new user. Body: `{"email": "...", "password": "..."}`.
Returns 201 with the user (without password hash). Returns 409 on duplicate email.

### `POST /api/v1/auth/token`

Status: `IMPLEMENTED`

OAuth2 password grant. Body: `username`, `password` as form fields.
Returns 200 with `{"access_token": "...", "token_type": "bearer"}`. Returns 401 on failure.

### `POST /api/v1/auth/me/member-link`

Status: `IMPLEMENTED`

Claims an existing member identity. Body: `{"phone_number": "...", "government_id": "..."}`.
Links the authenticated user to the member whose `phone_number` and `government_id` match.
Returns 200 with the updated user. Returns 404 if no match, 409 if already linked, 401 if unauthenticated.

### `GET /api/v1/auth/me`

Status: `IMPLEMENTED`

Returns the current authenticated user. Returns 401 if unauthenticated.

## Chamas

### `POST /api/v1/chamas`

Status: `IMPLEMENTED`

Creates a Chama. Also creates a member identity for the authenticated user, links them, and assigns `CHAIRPERSON`.
Body: `{"name": "...", "registration_fee_amount": "100.00", "member": {"first_name": "...", "last_name": "...", "phone_number": "...", "government_id": "..."}}`.
Returns 201 with the Chama. Returns 409 on duplicate phone, government ID, or user already linked.

### `GET /api/v1/chamas/{chama_id}`

Status: `IMPLEMENTED`

Returns a Chama only when the authenticated user is authorized (active membership).
Returns 403 if unauthorized, 404 if not found.

### `PATCH /api/v1/chamas/{chama_id}`

Status: `IMPLEMENTED`

Updates Chama details (name, registration fee amount). Only `CHAIRPERSON`.
Body: `{"name": "...", "registration_fee_amount": "..."}`. Fields are optional.
Returns 200 with the updated Chama. Returns 403 if not chairperson, 404 if not found.

## Memberships

### `POST /api/v1/chamas/{chama_id}/memberships`

Status: `IMPLEMENTED`

Adds a member to a Chama. Only `CHAIRPERSON`, `TREASURER`, or `SECRETARY`.
Server-side membership number is allocated transactionally.
Body: `{"member": {"first_name": "...", "last_name": "...", "phone_number": "...", "government_id": "..."}}`.
Returns 201 with the membership. Returns 409 on duplicate member/membership.

### `GET /api/v1/chamas/{chama_id}/memberships`

Status: `IMPLEMENTED`

Returns all memberships for the Chama, ordered by membership number.
Returns 403 if unauthorized, 404 if Chama not found.

### `PATCH /api/v1/chamas/{chama_id}/memberships/{membership_id}/status`

Status: `IMPLEMENTED`

Updates a membership's status (ACTIVE/INACTIVE). Only `CHAIRPERSON`.
Body: `{"status": "ACTIVE"}` or `{"status": "INACTIVE"}`.
Returns 200 with the updated membership.

## Roles

### `GET /api/v1/chamas/{chama_id}/roles`

Status: `IMPLEMENTED`

Returns all available roles. Any authorized member.

### `POST /api/v1/chamas/{chama_id}/memberships/{membership_id}/roles`

Status: `IMPLEMENTED`

Assigns a leadership role to a membership. Only `CHAIRPERSON`.
Body: `{"role": "TREASURER"}`. Role is one of `TREASURER`, `SECRETARY`.
Returns 201 with the updated membership.
Returns 409 if already assigned, 403 if not chairperson.

### `DELETE /api/v1/chamas/{chama_id}/memberships/{membership_id}/roles/{role_name}`

Status: `IMPLEMENTED`

Removes a leadership role from a membership. Only `CHAIRPERSON`.
Returns 200 with the updated membership. Returns 403 if not chairperson.

## Registration Fees

### `GET /api/v1/chamas/{chama_id}/memberships/{membership_id}/registration-fee`

Status: `IMPLEMENTED`

Returns the registration fee for a membership. Any authorized member.
Returns 404 if not found.

### `POST /api/v1/chamas/{chama_id}/memberships/{membership_id}/registration-fee/waive`

Status: `IMPLEMENTED`

Waives a registration fee (sets status to WAIVED). Only `CHAIRPERSON`.
Returns 200 with the updated fee.

## Contributions

### `POST /api/v1/chamas/{chama_id}/contributions`

Status: `IMPLEMENTED`

Records a contribution. Only `CHAIRPERSON` or `TREASURER`.
Body: `{"membership_id": "...", "amount": "1500.00", "period": "2026-09"}`.
Returns 201. Returns 409 on duplicate non-reversed contribution for the period.

### `GET /api/v1/chamas/{chama_id}/contributions`

Status: `IMPLEMENTED`

Returns all contributions for a Chama. Any authorized member.

### `POST /api/v1/chamas/{chama_id}/contributions/{contribution_id}/confirm`

Status: `IMPLEMENTED`

Confirms a contribution. Only `CHAIRPERSON`. Creates share records per ADR-005.
Returns 200. Returns 409 if not PENDING.

### `POST /api/v1/chamas/{chama_id}/contributions/{contribution_id}/reverse`

Status: `IMPLEMENTED`

Reverses a contribution. Only `CHAIRPERSON`. Deletes associated share records.
Returns 200. Returns 409 if not CONFIRMED.

## Shares

### `GET /api/v1/chamas/{chama_id}/memberships/{membership_id}/shares`

Status: `IMPLEMENTED`

Returns all shares for a membership. Any authorized member.
Returns 403 if unauthorized, 404 if membership not found.

## API rules

- Use versioned URLs.
- Validate input and output with Pydantic.
- Never trust client-supplied ownership, roles, balances, or Chama IDs.
- Return structured errors.
- Use appropriate HTTP status codes.
- Never expose passwords, hashes, secrets, or credentials.
- Membership views omit government IDs (public member schema only).