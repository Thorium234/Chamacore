# ADR-016: Provider Port and Payment Provider Adapters

## Status

Approved

## Decision

ChamaCore interacts with payment providers through a single interface
(`ProviderPort`) that isolates the domain from provider-specific HTTP APIs,
authentication flows, request formats, and callback shapes.

### Provider port contract

`app/providers/base.py` defines `ProviderPort` as a pure abstract class with
the following operations:

- `validate_credentials` — live-check credentials against the provider
  without leaking them; returns `CredentialValidationResult`.
- `create_payment_attempt` — ask the provider to initiate a charge against
  the customer's phone; returns `PaymentAttemptResult` with an accepted/rejected
  status and, when accepted, a `provider_request_id` for follow-up queries.
- `query_payment_status` — resolve the current provider status for a
  previously accepted request; returns `StatusQueryResult`.
- `parse_callback` — normalize a raw inbound callback into `ParsedCallback`
  domain values.
- `verify_callback` — apply the provider's documented signature mechanism;
  providers without a per-payload signature return `(True, None)` and rely
  on attempt binding, callback tokens, HTTPS, and deduplication.
- `normalize_provider_status` — map a provider status string to the
  normalized `ProviderTransactionStatus` enum.
- `masked_account_identifier` / `redact` — safe display and logging helpers.
- `decrypted_credentials` — validate and shape the sealed credential map for
  a provider call, rejecting unknown and missing keys.

The `ProviderSpec` dataclass describes static provider metadata (code, name,
capabilities, supported environments) and is exposed through a read-only
`spec` property.

### Jenga adapter (Finserve Africa)

`JengaAdapter` implements the api-checkout STK Push product documented at
Finserve Africa:

- Authentication: `POST {base}/authentication/api/v3/authenticate/merchant`
  with `Api-Key` header and merchant code + consumer secret.
- STK Push: `POST {base}/api-checkout/mpesa-stk-push/v3.0/init` with a
  Bearer token and optional `Signature` header.
- Status query: `GET {base}/api-checkout/mpesa-stk-push/v3.0/status/order/
  {orderReference}` with Bearer token.
- IPN callback: merchant-configured `payment.callbackUrl` receives a JSON
  payload with `orderReference`, `paymentReference`, `transactionId`, and
  `status`.

Phone normalization: the adapter normalizes Kenyan phone numbers to
`2547XXXXXXXX` (12-digit) form before sending to the provider.

Signature limitation (documented): the exact canonical string for the STK
Push signature is merchant-specific and must be confirmed with Jenga before
go-live. When a `signing_private_key` is configured in the sealed
credentials, the adapter signs the best-effort canonical concatenation using
RSA PKCS1v15 with SHA-256; when no key is configured, the `Signature` header
is omitted. The `attempt_signature` flag allows disabling signature attempts
entirely.

### Daraja adapter (Safaricom)

`DarajaAdapter` implements Lipa Na M-Pesa Online (STK Push):

- OAuth token: `GET /oauth/v1/generate?grant_type=client_credentials` with
  HTTP Basic authentication. Tokens last approximately 1 hour.
- STK Push: `POST /mpesa/stkpush/v1/processrequest` with Bearer token and
  a `Password = base64(ShortCode + Passkey + Timestamp)` where timestamp is
  EAT `YYYYMMDDHHmmss`.
- Status query: `POST /mpesa/stkpushquery/v1/query` keyed on
  `CheckoutRequestID`.
- Callback payload: `Body.stkCallback` with `CheckoutRequestID`,
  `ResultCode` (0 = success), and `CallbackMetadata.Item` metadata array.

Daraja requires a whole-number KES amount; decimal amounts are rejected with
`AMOUNT_NOT_INTEGER`.

Known failure result codes are mapped to human-readable messages (e.g. 1 =
insufficient balance, 1032 = customer cancelled, 1037 = USSD timeout).

### Provider registry

`app/providers/registry.py` provides a `ProviderRegistry` keyed by
`(PaymentProviderCode, PaymentEnvironment)`. A sandbox adapter instance
can never be used to reach a production endpoint because the environment is
baked into the adapter at construction time.

`build_default_registry()` lazily imports and registers both Jenga and Daraja
adapters for both `SANDBOX` and `PRODUCTION` environments.

### Raw body handling

The webhook endpoint reads the raw payload via `Request.body()` rather than
`Body(bytes)`, which avoids a FastAPI/Starlette JSON-content-type conflict
when the provider sends `application/json`.

### Credential sealing

Provider credentials are never stored in plaintext. The payment connection
service encrypts them with AES-256-GCM (AAD scoped to `connection_id` +
`credential_version`) via `CredentialCipher`. The sealed ciphertext, key
version, and masked account identifier are the only credential artifacts
persisted.

### Documented limitations

- Jenga IPN payload/signature contract is merchant-specific; the adapter
  relies on attempt binding, callback tokens, HTTPS, and deduplication for
  callback security.
- Daraja provides no per-payload signature or hash; the same documented
  controls apply.

## Reason

Payment providers expose different HTTP APIs, authentication mechanisms,
callback shapes, and idiosyncrasies. A provider-neutral port boundary
prevents provider details from leaking into the contribution, intent, or
ledger services, keeps the domain testable without live network access, and
allows new providers to be added without changing the payment domain model.

## Consequences

- The payment domain depends only on `app/providers/base.py`; no concrete
  adapter is imported by services or endpoints.
- Adapters are independently testable using `httpx.MockTransport` (53
  contract tests).
- Two adapter bugs were discovered and fixed during contract testing:
  `JengaAdapter.decrypted_credentials` raised `KeyError` on the optional
  `signing_private_key` field, and `DarajaAdapter.validate_credentials`
  propagated `ProviderIntegrationError` instead of returning an invalid
  result.
- Phone normalization failures are validated before initiating a provider
  call where possible; Jenga normalizes after authentication.
