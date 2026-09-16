# ADR-017: Payment Connection Lifecycle

## Status

Approved

## Decision

A Chama connects to a payment provider through a **payment connection** with
a controlled, audited lifecycle. Connections are Chama-scoped and modelled by
the `PaymentConnection` row plus an append-only `PaymentConnectionAudit`
history.

### Connection identity and uniqueness

A connection is unique per `(chama_id, provider_code, environment)`. Each
connection stores:

- sealed credentials (AES-256-GCM ciphertext, encryption key version,
  credential version),
- a masked account identifier for display,
- per-connection secret callback token (used by the webhook service),
- lifecycle timestamps and the actor (`created_by_user_id`,
  `updated_by_user_id`).

No endpoint or schema ever returns the raw credentials or the ciphertext.

### Statuses

`PaymentConnectionStatus` is one of:

- `PENDING_VALIDATION` — created/replaced, not yet verified against the
  provider.
- `ACTIVE` — credentials validated; accepts new payment attempts.
- `DISABLED` — manually disabled; validation is allowed for testing but the
  status never automatically transitions to `ACTIVE`.
- `INVALID` — last validation failed.

Transitions:

- create → `PENDING_VALIDATION`
- replace → bumps `credential_version`, resets status to
  `PENDING_VALIDATION`, and seals the new credentials
- validate succeeds → `ACTIVE`
- validate fails → `INVALID`
- validate on a `DISABLED` connection → stays `DISABLED` (test-only; status
  never auto-activates)
- disable → `DISABLED` (idempotent)

### Authorization

- **Chairperson** may create, replace, disable, and delete a connection.
- **Any active member** of the Chama may list and read connections and may
  run validation.
- Every read path is Chama-scoped: a member of one Chama can never see or
  mutate another Chama's connections (verified by tests).

### Credential handling

- Credentials payloads are strictly validated: required fields per adapter
  must be present and no unexpected fields are allowed.
- `CredentialCipher` seals credentials with AES-256-GCM, keyed in part to
  `connection_id` and `credential_version`, so a credential blob is useless
  outside its connection.
- Rotation works: decrypting with the previous key version still opens old
  blobs until the rotation windows out old keys; the current version requires
  the current key master.

### Validation and rate limiting

`POST /chamas/{chama_id}/payment-connections/{connection_id}/validate`:

- is rate-limited per Chama (5 allowed rapid attempts, then `429`),
- uses the adapter's `validate_credentials` and records the outcome as an
  audit event with a safe error message,
- never returns provider secrets, error messages, or internal details.

### Deletion

`DELETE /chamas/{chama_id}/payment-connections/{connection_id}`:

- is chairperson-only,
- is blocked (`409 CONFLICT`) if the connection has payment history (any
  intent attempt or webhook event), so confirmed financial records can never
  be silently destroyed,
- otherwise removes the row and appends a `DELETED` audit event.

The audit table foreign key is `ON DELETE CASCADE` so deleting a connection
with no financial history cannot be blocked by its own lifecycle audit rows.

### Audit trail

Every lifecycle transition appends a `PaymentConnectionAudit` row with the
actor user id, action, previous and new status, and credential version.

## Reason

Payment credentials are the most sensitive configuration a Chama holds. The
connection lifecycle gives Chamas a safe, controllable, and audited way to
provision a provider without ever exposing secrets, and prevents accidental
use of unverified credentials.

## Consequences

- All credential mutations are chairperson-only; misuse of roles is rejected.
- Validation must be deliberately run before any payment attempt can use a
  connection.
- Deleting a connection with financial history is impossible by design; the
  documented alternative is to leave it in place or disable it.
- Tests cover: create, secrets never exposed (API and DB), duplicate
  provider/environment conflict, cross-Chama 403, validate transitions,
  active-revalidate rejection, rate limits, replace version bumps, disable
  idempotency, delete-with and without history, and member-level reads.