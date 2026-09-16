# ADR-018: Webhook Inbox and Payment Event Deduplication

## Status

Approved

## Decision

Provider callbacks arrive at a single unauthenticated endpoint —

`POST /api/v1/payments/webhooks/{provider_code}/{environment}`

— and are processed by `PaymentWebhookService.handle` as an append-only,
deduplicated event inbox, bound to payment intents and attempts.

### Input handling

- The endpoint reads the raw payload via `Request.body()` (not
  `Body(bytes)`) so providers sending `application/json` are not
  JSON-parsed by FastAPI.
- A size limit (max body) applies and oversized callbacks are rejected.
- The endpoint is rate-limited by `(provider_code, environment, client IP)`;
  excessive callbacks get `429 TOO_MANY_REQUESTS`.

### The seven step pipeline

On each callback the service performs:

1. **Size check** — reject oversized payloads.
2. **Connection resolution** — resolve the connection by the per-connection
   callback token (`?callback_token=<token>` query parameter) first, then by
   attempt binding (`provider_request_id` / `provider_transaction_id`) when
   no token is present. Unknown tokens or connections are rejected.
3. **Provider verification** — call the adapter's documented verification.
   Providers without a per-payload signature (`JengaAdapter`,
   `DarajaAdapter`) return pass-through and the pipeline relies on token
   binding, HTTPS, amount matching, and deduplication (documented
   limitations).
4. **Event identity** — compute a SHA-256 hash of the raw payload and build
   `(provider_code, environment, provider_event_id)` as the event identity.
5. **Deduplication** — a partial unique index on
   `(connection_id, provider_event_id)` and a unique-event check ensure a
   callback is processed once. A duplicate with the *same event id and same
   payload hash* returns `DEDUPLICATED`; a duplicate event id with a
   **different** payload hash returns `DISAGREEMENT`, so conflicting callbacks
   from a provider are recorded rather than silently resolved.
6. **Raw payload storage** — the raw callback bytes are stored in
   `payment_events.raw_payload` with its hash for audit and replays.
7. **State transition** — the callback is bound to a matching attempt (by
   `provider_request_id`, then `provider_transaction_id`), the amount and
   currency are compared to the attempt, and on match the attempt and intent
   state machines advance atomically. Amount or currency mismatches produce
   `DISAGREEMENT`. Callbacks referencing an already-terminal attempt are
   consistency-checked and stored without corrupting state.

### Event statuses

`PaymentEventStatus` is one of:

- `RECEIVED` — payload accepted and stored.
- `PROCESSED` — bound to an attempt and applied to the intent state.
- `DEDUPLICATED` — exact duplicate of a previously processed callback.
- `REJECTED` — verification failed or unknown connection/token.
- `UNPROCESSABLE` — payload could not be parsed or matched.
- `DISAGREEMENT` — conflicting payload for a known event id, or amount /
  currency mismatch against the attempt.

### Out-of-order handling

Callbacks that report a *failed* payment for an attempt that is not in a
terminal success state are recorded and the attempt is failed while the
intent stays in `PROCESSING` (the intent is only finalised on success, by a
success callback, or by a query that reaches a terminal state). Already-final
attempts are consistency-checked rather than re-transitioned.

## Reason

Provider callbacks are network-triggered, unstructured, and can arrive
duplicated, re-ordered, forged, or for transactions another connection
created. An append-only inbox with a strict identity check gives the system a
provable, replay-safe record of every callback and a deterministic binding to
the payment attempt that was created by us.

## Consequences

- Every accepted callback is stored verbatim, so audits and replays are
  possible.
- Replaying the same callback is safe (idempotent by event identity).
- A callback that conflicts in payload or amount is recorded as
  `DISAGREEMENT`, never silently applied.
- Attempts are only advanced when the callback is bound to a known attempt
  and matches its amount/currency.
- Tests cover: success processing, deduplication, disagreement detection,
  verification failure, missing-token fallback to attempt binding,
  invalid token, nonexistent connection, amount/currency mismatch, and failed
  callbacks leaving the intent in `PROCESSING`.