# ChamaCore API Contract

## Status labels

- `PLANNED`: documented but not implemented
- `IMPLEMENTED`: implemented and tested
- `DEPRECATED`: no longer valid

## Root

### `GET /`

Status: `IMPLEMENTED`

Returns a landing payload with the service name, version, and API docs path:
`{"service": "ChamaCore", "version": "1.0.0", "docs": "/docs"}`. In production
builds (`CHAMACORE_DEBUG=false`) the `docs` key is omitted.

## Health and Readiness

### `GET /health`

Status: `IMPLEMENTED`

Returns `{"status": "ok"}`. No database check.

### `GET /ready`

Status: `IMPLEMENTED`

Returns `{"status": "ready"}`. Verifies database connectivity.

### `GET /metrics`

Status: `IMPLEMENTED`

Returns a Prometheus text exposition of process-level HTTP metrics
(`chamacore_http_requests_total`, `chamacore_http_request_duration_seconds_*`)
with bounded route-template labels. In production
(`CHAMACORE_DEBUG=false`) the endpoint requires the `X-Metrics-Token` header
matching `CHAMACORE_METRICS_TOKEN`; without a matching token it returns 404.
If `CHAMACORE_METRICS_TOKEN` is unset the endpoint returns 404 so the scrape
path is never public. Debug builds leave it open. Intended for an internal
monitoring scraper only.

## Request correlation

Every response carries an `X-Request-ID` header. If the client supplied one
on the request, it is echoed back; otherwise the server generates one. All
log records for the request carry the same value.

## Authentication

### `POST /api/v1/auth/register`

Status: `IMPLEMENTED`

Registers a new user. Body: `{"email": "...", "password": "..."}`.
Returns 201 with the user (without password hash). Returns 409 on duplicate email.

### `POST /api/v1/auth/token`

Status: `IMPLEMENTED`

OAuth2 password grant. Body: `username`, `password` as form fields.
Returns 200 with `{"access_token": "...", "refresh_token": "...", "token_type":
"bearer", "expires_in": 7200}`. `expires_in` seconds equals
`CHAMACORE_JWT_EXPIRES_MINUTES` (default 120). Returns 401 on failure. The
system posting account (`system@chamacore.invalid`) always fails login.

### `POST /api/v1/auth/refresh`

Status: `IMPLEMENTED`

Exchanges an unused, unexpired refresh token for a fresh access token **and**
a rotated refresh token (the presented token is revoked). Body:
`{"refresh_token": "..."}`. Returns 200 with the same `TokenOut` shape as
`/token`. Refresh tokens are single-use and rotate: presenting the same token
twice (or a revoked/expired/unknown one) returns 401, so a replay collapses
the session. Rate-limited per client IP.

### `POST /api/v1/auth/logout`

Status: `IMPLEMENTED`

Revokes the presented (still valid) refresh token. Body:
`{"refresh_token": "..."}`. Returns 204. Idempotent — the presented token is
made unusable regardless of its previous state.

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

## Ledger (V2)

### `GET /api/v1/chamas/{chama_id}/ledger`

Status: `IMPLEMENTED`

Returns the Chama's financial transaction history (ledger transactions with
their debit/credit entries). Any active member of the Chama.

**Query parameters:**
- `limit` (int, 1–100, default 25) — page size.
- `cursor` (string, optional) — opaque cursor from a previous response.

**Response (`LedgerHistoryOut`):**
```json
{
  "items": [
    {
      "id": "uuid",
      "chama_id": "uuid",
      "source_type": "CONTRIBUTION",
      "source_id": "uuid",
      "description": "...",
      "posted_by_user_id": "uuid",
      "reverses_transaction_id": null,
      "created_at": "2026-09-16T09:37:34",
      "entries": [
        {
          "account_id": "uuid",
          "account_code": "1000",
          "account_name": "Cash",
          "debit": "100.00",
          "credit": "0.00"
        }
      ]
    }
  ],
  "next_cursor": "eyJ0...",
  "has_more": true
}
```

Amounts are decimal strings with two decimal places. Cursor pagination is
keyset-based on `(created_at DESC, id DESC)`. The cursor is a base64-encoded
JSON object containing a timestamp and transaction ID.

Returns 422 if the cursor is malformed, 403 if the caller has no active
membership, 404 if the Chama does not exist.

### `GET /api/v1/chamas/{chama_id}/ledger/accounts`

Status: `IMPLEMENTED`

Returns the Chama's ledger accounts with their current balances. Any active
member of the Chama.

**Response (`LedgerAccountsOut`):**
```json
{
  "items": [
    {
      "id": "uuid",
      "code": "1000",
      "name": "Cash",
      "account_type": "ASSET",
      "description": null,
      "balance": "150.00"
    }
  ]
}
```

Balances are signed decimals computed on demand from posted entries as
`sum(debit) - sum(credit)` per account, quantized to two decimal places
(`SignedMoney`; assets read positive, equity/revenue read negative). No
balance is ever stored or maintained as a competing financial truth.

Returns 403 if the caller has no active membership, 404 if the Chama does not
exist.

### `GET /api/v1/chamas/{chama_id}/ledger/accounts/{account_id}/entries`

Status: `IMPLEMENTED`

Returns one account with a cursor-paginated list of its posted entries
(oldest-first within the account, keyset on `(created_at, id)`).

**Query parameters:**
- `limit` (int, 1–100, default 25) — page size.
- `cursor` (string, optional) — opaque cursor from a previous response.

**Response (`LedgerAccountEntriesOut`):**
```json
{
  "account": { "id": "uuid", "code": "1000", "name": "Cash",
               "account_type": "ASSET", "description": null, "balance": "150.00" },
  "items": [
    { "id": "uuid", "transaction_id": "uuid", "source_type": "CONTRIBUTION_CONFIRMATION",
      "source_id": "uuid", "description": "...", "debit": "150.00",
      "credit": "0.00", "created_at": "2026-09-16T09:37:34" }
  ],
  "next_cursor": "eyJ0...",
  "has_more": false
}
```

Returns 404 if the account does not exist or belongs to another Chama, 403 if
the caller has no active membership, 422 if the cursor is malformed.

Posting rules: there is no public endpoint that writes to the ledger. Ledger
entries are created only by the trusted posting service when an approved
business event is posted (ADR-012).

## Payments (V3)

Payment endpoints live under `/api/v1`. Connections management is
chairperson-only; intents and attempts are readable by any active member and
initiation selects an ACTIVE connection. Credentials are never returned.

### Payment connections (ADR-017)

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/api/v1/chamas/{chama_id}/payment-connections` | Create a sealed connection (provider, environment, credentials). Chairperson. |
| `GET` | `/api/v1/chamas/{chama_id}/payment-connections` | List connections. Any active member. |
| `GET` | `/api/v1/chamas/{chama_id}/payment-connections/{connection_id}` | One connection. Any active member. |
| `POST` | `/api/v1/chamas/{chama_id}/payment-connections/{connection_id}/validate` | Validate credentials → ACTIVE. Chairperson. |
| `PATCH` | `/api/v1/chamas/{chama_id}/payment-connections/{connection_id}` | Replace credentials (new credential version). Chairperson. |
| `POST` | `/api/v1/chamas/{chama_id}/payment-connections/{connection_id}/disable` | Idempotent disable. Chairperson. |
| `DELETE` | `/api/v1/chamas/{chama_id}/payment-connections/{connection_id}` | 204. Blocked when financial history exists. Chairperson. |

Connection lifecycle: `PENDING_VALIDATION → ACTIVE | INVALID`, with
`replace() → PENDING_VALIDATION` (new version) and `disable() → DISABLED`.
Every transition appends a `PaymentConnectionAudit` row. `PaymentConnectionOut`
exposes only provider code, environment, status, masked account identifier,
key/credential versions, validation info, and timestamps.

### Payment intents and attempts (ADR-016)

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/api/v1/chamas/{chama_id}/payment-intents` | 201. Body: `membership_id`, `amount`, `currency` (default KES), `purpose`, `idempotency_key`, optional `contribution_id`. Idempotent by `(chama_id, idempotency_key)` with payload-hash matching. |
| `GET` | `/api/v1/chamas/{chama_id}/payment-intents` | List intents. Any active member. |
| `GET` | `/api/v1/chamas/{chama_id}/payment-intents/{intent_id}` | One intent. Any active member. |
| `POST` | `/api/v1/chamas/{chama_id}/payment-intents/{intent_id}/initiate` | Body: `connection_id`. Starts an STK Push attempt against an ACTIVE connection (first or retry). |
| `GET` | `/api/v1/chamas/{chama_id}/payment-intents/{intent_id}/attempts` | List attempts for an intent. Any active member. |
| `GET` | `/api/v1/chamas/{chama_id}/payment-attempts/{attempt_id}` | One attempt across the Chama. Any active member. |

Intent states: `PENDING → PROCESSING → SUCCEEDED | FAILED` (controlled).
Attempt states include per-provider terminal outcomes (`PERMANENT_FAILURE`
for known non-retryable errors, `TIMEOUT` with no provider request id, etc.);
at most one attempt in flight; retry only after transient failure. A
`provider_transactions` row records normalized status + raw provider response
for offline resolution.

### STK settlement (ADR-019)

A payment intent whose attempt reaches `SUCCEEDED` settles its linked
`contribution_id` (created as a contribution against the intent's membership)
as the system user, idempotently, posting DR Cash / CR Share Capital. A
succeeded intent without a linked contribution is a documented no-op (a
system posting requires a settled contribution object); a duplicate success
callback is an idempotent retry.

## Payments callbacks (V3)

Provider callbacks arrive unauthenticated and are bound to a Chama's payment
connection with the per-connection callback token (`?token=<...>`, derived
from `connection_callback_token`, ADR-018). There is currently a single active
provider, Daraja (sandbox and production).

### `POST /api/v1/payments/c2b/validate/{connection_id}`

Status: `IMPLEMENTED` (ADR-019)

Daraja C2B (manual Paybill) Validation URL for the Daraja Register-URL
activation step. Safaricom calls this before completing a payment.

**Query parameters:** `token` (required) — per-connection callback token.

**Request:** raw JSON, strict schema (`C2BCallbackBody`), `TransactionType`,
`TransID`, `TransTime`, `TransAmount`, `BusinessShortCode`, `BillRefNumber`,
`MSISDN`, and payer names are captured; a `TransID` is required, otherwise the
request is unprocessable.

**Response (`C2BValidationResponse`), always HTTP 200:**
```json
{ "ResultCode": 0, "ResultDesc": "Accepted" }
```

Accept logic (approved rule, OQ-021 / ADR-019): the payment is accepted
(`ResultCode = 0`) only when the `BillRefNumber` matches the membership number
of an ACTIVE membership on an ACTIVE payment connection; everything else is
rejected (`ResultCode = 1`). Every arrival is recorded as a `payment_event`
(identity `C2B_VALIDATION:<TransID>`) with its decided `ResultCode`, so every
arrival is auditable. Unknown connections/tokens are answered `ResultCode = 1`
(never a 404/500).

### `POST /api/v1/payments/c2b/confirm/{connection_id}`

Status: `IMPLEMENTED` (ADR-019)

Daraja C2B (manual Paybill) Confirmation URL. Called by Safaricom after a
payment completes.

**Query parameters:** `token` (required).

**Request:** same strict schema as validation.

**Response (`C2BConfirmationResponse`):**
```json
{ "ok": true, "event_id": "<uuid>", "event_status": "PROCESSED" }
```

- The raw payload and its SHA-256 hash are stored in `payment_events`
  (identity `C2B_CONFIRMATION:<TransID>`).
- Idempotent: a duplicate delivery of the same `TransID` + identical payload
  returns event_status `DEDUPLICATED`; the same `TransID` with a different
  payload returns event_status `DISAGREEMENT`.
- `BusinessShortCode` is compared to the connection's stored short code; a
  mismatch is recorded and acknowledged as event_status `UNPROCESSABLE` (the
  payment is not ours to settle).
- Settlement (ADR-019): confirmation records a **confirmed contribution** for
  that membership number's current `YYYY-MM` period and posts the ledger
  entry (DR `1000` Cash / CR `3000` Share Capital) as the system user
  (`system@chamacore.invalid`). Duplicate/re-delivered confirmations are
  deduplicated — one contribution and one ledger posting per `TransID`.
- Invalid/unknown tokens return `400 WEBHOOK_REJECTED`.

### `POST /api/v1/payments/webhooks/{provider_code}/{environment}`

Status: `IMPLEMENTED` (ADR-018)

Async callback inbox for intent-bound callbacks (e.g. STK Push callbacks).
Uses the seven-step pipeline: size check, connection resolution, verification,
event identity, deduplication, raw storage, state transition.

### `POST /api/v1/chamas/{chama_id}/payment-connections/{connection_id}/register-c2b-urls`

Status: `IMPLEMENTED`

Chairperson-only. Asks Daraja to bind the connection's shortcode to this
app's C2B Validation/Confirmation URLs (the "Register URL" step of the C2B
API). Runs server-side, so the operator never handles the credential
encryption key; `scripts/register_daraja_c2b_urls.py` drives it with a
chairperson login.

**Request (`C2BRegisterUrlRequest`):**
```json
{ "response_type": "Completed" }
```
`response_type` is `Completed` (default) or `Cancelled`.

**Response (`C2BRegisterUrlOut`):**
```json
{
  "accepted": true,
  "response_code": "0",
  "response_description": "Success",
  "validation_url": "https://<public>/api/v1/payments/c2b/validate/<connection_id>?token=...",
  "confirmation_url": "https://<public>/api/v1/payments/c2b/confirm/<connection_id>?token=..."
}
```

The URLs are derived from `CHAMACORE_PUBLIC_BASE_URL` + `CHAMACORE_API_V1_PREFIX`
and carry that connection's callback token. Safaricom requires the URLs to be
public and HTTPS in production. A provider rejection is surfaced as
`400 INVALID_STATE` with the provider's error code in the message. Returns
`403` for non-chairpersons.

## API rules

- Use versioned URLs.
- Validate input and output with Pydantic.
- Never trust client-supplied ownership, roles, balances, or Chama IDs.
- Return structured errors.
- Use appropriate HTTP status codes.
- Never expose passwords, hashes, secrets, or credentials.
- Membership views omit government IDs (public member schema only).