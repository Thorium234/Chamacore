# V1 API Contract

## Status labels

- `PLANNED`: documented but not implemented
- `IMPLEMENTED`: implemented and tested
- `DEPRECATED`: no longer valid

## Root endpoint

### `GET /`

Status: `IMPLEMENTED`

Current response:

```json
{"message": "Hello World"}
```

This temporary endpoint should eventually become a health endpoint.

## Chamas

### `POST /api/v1/chamas`

Status: `PLANNED`

Creates a Chama.

### `GET /api/v1/chamas/{chama_id}`

Status: `PLANNED`

Returns a Chama only when the authenticated user is authorized.

## Memberships

### `POST /api/v1/chamas/{chama_id}/memberships`

Status: `PLANNED`

Creates a membership and allocates a server-side membership number.

### `GET /api/v1/chamas/{chama_id}/memberships`

Status: `PLANNED`

Returns authorized memberships for the Chama.

## Contributions

### `POST /api/v1/chamas/{chama_id}/contributions`

Status: `PLANNED`

Records a contribution against a membership.

## Shares

### `GET /api/v1/chamas/{chama_id}/memberships/{membership_id}/shares`

Status: `PLANNED`

Returns shares belonging to the membership.

## API rules

- Use versioned URLs.
- Validate input and output with Pydantic.
- Never trust client-supplied ownership, roles, balances, or Chama IDs.
- Return structured errors.
- Use appropriate HTTP status codes.
- Never expose passwords, hashes, secrets, or credentials.