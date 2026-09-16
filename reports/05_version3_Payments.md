# ChamaCore V3 Payment Architecture — Coding Agent Prompt

You are continuing work on ChamaCore.

## Repository baseline

The latest repository commit is:

```text
b74d82215bbba17b84b680b51954a9969940ef6a
Harden V2 ledger per implementation review
```

V1 is complete. V2 contains the ledger foundation and ledger hardening.

Before starting V3, verify the repository yourself:

```text
SQLite: 109 tests passed
SQLite migrations: passed
SQLite Alembic check: passed
Python compile check: passed
PostgreSQL migration: passed
```

There is one known verification blocker in the current commit:

- The PostgreSQL migration creates ledger guard triggers.
- `tests/conftest.py` creates the same triggers again for every PostgreSQL
  fixture.
- PostgreSQL tests therefore fail with duplicate-trigger errors before the
  application tests can run.
- When the already-migrated duplicate triggers are removed before the test
  fixture creates them, the PostgreSQL application tests pass:
  `107 passed, 2 deselected`, plus `2 concurrency tests passed`.

Fix this test/migration trigger setup before claiming the baseline is green.
Make trigger creation idempotent or make the PostgreSQL fixture reuse the
migration-created guards. Do not weaken the production database protections.
Then run:

```bash
pytest -q
CHAMACORE_DATABASE_URL=<postgres-url> alembic upgrade head
CHAMACORE_DATABASE_URL=<postgres-url> pytest -q -m "not concurrency"
CHAMACORE_DATABASE_URL=<postgres-url> pytest -q -m concurrency
alembic check
```

## Mission

Begin V3: **Payment Architecture**.

The payment system must support multiple payment gateways without changing
ChamaCore's business domain every time a provider is added.

The first provider work will be:

1. Jenga as the first implementation.
2. Daraja sandbox as the next implementation.
3. Daraja STK Push for contribution payment initiation.

The architecture must make adding later providers possible without copying
provider-specific code into contributions, the ledger, loans, or payouts.

## Non-negotiable product requirement: Chairperson-configured credentials

The chairperson must be able to configure a Chama's payment-provider
credentials once through the application.

This means credentials are entered through an authenticated application
flow—not pasted into chat, source code, logs, issue trackers, fixtures, or
normal environment configuration.

The credential design must meet all of these requirements:

1. Only an active Chairperson of that Chama may create, replace, test, rotate,
   revoke, or delete that Chama's provider connection.
2. A Chama can have separate connections for Jenga, Daraja sandbox, Daraja
   production, and future providers.
3. Credentials must be encrypted before persistence.
4. The encryption master key must come from a Replit-managed environment
   secret, such as `CHAMACORE_CREDENTIAL_ENCRYPTION_KEY`.
5. Never store provider secrets as plaintext in PostgreSQL, SQLite, logs,
   traces, exception messages, HTTP recordings, test snapshots, or API
   responses.
6. Never return a raw credential after creation. Read endpoints may return
   only provider name, environment, status, masked identifiers, timestamps,
   and validation state.
7. Use authenticated encryption with a random nonce, key version, and
   associated data containing at least the Chama ID, provider code,
   environment, and credential record version.
8. Support key rotation without requiring all providers to be re-entered at
   once.
9. Store only the provider fields actually required by the adapter.
10. Validate credentials against the provider before marking the connection
    usable.
11. Record failed validation without exposing the submitted secret.
12. Separate sandbox and production credentials and endpoints. Never allow a
    sandbox connection to call a production endpoint or vice versa.
13. Make the credential input schema provider-specific and use secret-aware
    types such as `SecretStr`; prevent secrets from appearing in model reprs.
14. Include an explicit revoke/disable flow. Revoking a connection must stop
    new payment attempts while preserving historical payment records.
15. Audit who created, replaced, tested, rotated, revoked, or enabled a
    connection, without recording the secret itself.

Do not use a single global gateway credential for all Chamas. Credentials are
owned by a Chama-provider-environment connection.

## Required reading before coding

Read all of the following:

1. `AGENTS.md`
2. `docs/00_PROJECT_STATUS.md`
3. `docs/01_PRODUCT_REQUIREMENTS.md`
4. `docs/02_DOMAIN_MODEL.md`
5. `docs/03_BUSINESS_RULES.md`
6. `docs/04_DATABASE.md`
7. `docs/05_ARCHITECTURE.md`
8. `docs/06_API_CONTRACT.md`
9. `docs/08_ROADMAP.md`
10. `docs/10_V2_FINANCIAL_CORE.md`
11. `docs/decisions/OPEN_QUESTIONS.md`
12. ADR-010 through ADR-015
13. The current V2 report and V2 ledger implementation

Before coding, create or update:

- `docs/11_V3_PAYMENT_ARCHITECTURE.md`
- `docs/decisions/ADR-016-payment-domain-and-provider-abstraction.md`
- `docs/decisions/ADR-017-provider-credentials-and-secret-encryption.md`
- `docs/decisions/ADR-018-payment-idempotency-and-webhooks.md`
- `docs/decisions/OPEN_QUESTIONS.md`
- `reports/05_v3_payment_architecture.md`

Do not put provider credentials in any documentation or example.

## Required architecture

### 1. Provider-neutral domain

The core domain must not import Jenga or Daraja SDKs, request models, status
names, URLs, OAuth details, or callback payloads.

Define provider-neutral ports/interfaces for capabilities such as:

```text
validate_credentials
create_payment_attempt
query_payment_status
parse_callback
verify_callback
normalize_provider_status
```

Use a provider registry/factory to resolve an adapter by:

```text
provider_code
environment
capability
```

Provider adapters may contain provider-specific HTTP and authentication logic.
The payment service must depend on the port, not on a concrete provider.

Do not create an abstraction that assumes every provider supports STK Push.
Capabilities must be explicit. For example:

```text
STK_PUSH
PAYMENT_REQUEST
PAYMENT_STATUS_QUERY
CALLBACKS
REFUNDS
```

Jenga and Daraja may expose different capabilities and different lifecycle
details. The domain must handle that through capability checks, not provider
conditionals spread across services.

### 2. Gateway connections

Create a Chama-scoped provider connection model with at least:

```text
id
chama_id
provider_code
environment: SANDBOX | PRODUCTION
status: PENDING_VALIDATION | ACTIVE | DISABLED | INVALID
encrypted_credentials
encryption_key_version
credential_version
masked_account_identifier
last_validated_at
last_validation_error_code
created_by_user_id
updated_by_user_id
created_at
updated_at
```

Enforce:

```text
UNIQUE(chama_id, provider_code, environment)
```

Do not expose `encrypted_credentials` through ORM response schemas.

### 3. Payment intent and attempts

Do not make a provider request directly from the contribution endpoint.

Create a provider-neutral payment domain with separate records for:

- `payment_intents` — the business-level request to collect money
- `payment_attempts` — each provider attempt, including retries
- `provider_transactions` — provider identifiers and normalized status
- `payment_events` — inbound callbacks/webhooks and deduplication metadata

At minimum, payment intents should retain:

```text
id
chama_id
membership_id or approved business reference
contribution_id when the approved V2 rule permits the link
amount
currency
purpose
status
idempotency_key
created_by_user_id
created_at
updated_at
```

At minimum, attempts should retain:

```text
id
payment_intent_id
connection_id
attempt_number
provider_request_id
provider_transaction_id
client_reference
status
failure_code
failure_message_safe
requested_at
completed_at
```

The exact fields and statuses require an ADR. Do not silently invent
accounting or payment semantics.

### 4. State machines

Define explicit, database-backed status values and allowed transitions for:

- provider connection
- payment intent
- payment attempt
- provider transaction
- inbound payment event

Clients must not be allowed to set `SUCCEEDED`, `CONFIRMED`, `REVERSED`, or
equivalent final statuses.

A provider callback must not automatically be treated as trusted money
confirmation without provider-specific verification and a server-side status
policy.

Every transition must:

- validate the current state,
- be idempotent,
- record the actor/source,
- preserve history,
- reject illegal regressions,
- be safe under concurrent callbacks and retries.

### 5. Idempotency and duplicate protection

Implement idempotency at every boundary:

1. Client payment-intent request.
2. Provider payment attempt.
3. Provider callback/webhook.
4. Provider status query retry.
5. Contribution confirmation.
6. Ledger posting.

Use separate keys for separate concerns. At minimum:

```text
client idempotency key per Chama and operation
provider request/reference ID
provider event ID
payment intent ID
payment attempt ID
```

Enforce uniqueness in the database, not only in Python.

If the same idempotency key is reused with a different normalized payload,
return a conflict. Never silently return the first result for a changed
amount, membership, currency, provider, or purpose.

### 6. Webhooks and callbacks

Provider callbacks must be handled through provider-specific adapters and a
provider-neutral event inbox.

For every callback:

1. Receive the raw request.
2. Authenticate or verify it using the provider's official mechanism.
3. Apply replay protection and timestamp checks where supported.
4. Calculate and store a payload hash.
5. Deduplicate using the provider event identifier and provider connection.
6. Parse into a normalized internal event.
7. Store the raw payload only under the approved retention and privacy policy.
8. Apply the state transition in a transaction.
9. Return the provider-required response.
10. Never include secrets in the response or logs.

Do not rely only on IP allowlists. Do not assume Daraja and Jenga use the
same callback verification rules. Read the official provider documentation
for each adapter and record any limitation in the provider ADR.

The webhook endpoint must be safe when:

- the same callback is delivered many times,
- callbacks arrive out of order,
- a callback arrives after a timeout,
- a callback arrives after a connection is disabled,
- two callbacks are processed concurrently,
- the provider status disagrees with the local status.

### 7. Jenga-first implementation

Implement Jenga as the first real adapter behind the provider interface.

Before implementing HTTP calls:

- identify the exact Jenga sandbox environment,
- document authentication and token expiry,
- document request signing or headers,
- document request and callback identifiers,
- document timeout and retry rules,
- document status mapping,
- document callback verification,
- document sandbox limitations,
- document the official API version and base URL.

Do not hard-code Jenga behavior into contribution or payment services.

Create:

- a Jenga credential schema,
- Jenga credential validation,
- a Jenga adapter,
- normalized request/response mapping,
- safe error mapping,
- mocked contract tests,
- sandbox integration tests behind an explicit opt-in flag.

Never make real provider calls during the normal unit test suite.

### 8. Daraja sandbox and STK Push

Implement Daraja as a second adapter, not as a special case inside Jenga or
the contribution service.

Daraja sandbox must support the STK Push capability through the provider
interface:

```text
create STK Push request
receive and verify callback
normalize callback result
query status when callback is delayed or ambiguous
```

Document and test:

- OAuth token acquisition and expiry,
- consumer key and consumer secret handling,
- short code and passkey handling,
- transaction type,
- amount and currency rules,
- phone-number normalization,
- account/reference fields,
- callback URL,
- checkout request ID,
- merchant request ID,
- result codes,
- timeout behavior,
- retry behavior,
- callback deduplication.

Keep Daraja sandbox and production configuration separate. A sandbox
connection must never call production.

Do not mark a contribution as confirmed merely because an STK Push request
was accepted. “Request accepted”, “customer prompted”, “payment completed”,
“payment failed”, and “status unknown” are different states.

### 9. Contribution and ledger boundaries

The current repository intentionally leaves contribution-to-ledger posting
blocked by OQ-012 and OQ-013. V3 must preserve that rule.

Do not:

- mark a contribution `CONFIRMED` from a client request,
- mark it confirmed from an unverified callback,
- create shares before the approved confirmation transition,
- post ledger entries before the approved account mapping exists,
- create payment-provider-specific ledger accounts,
- make the ledger depend on Jenga or Daraja identifiers.

The intended eventual flow is:

```text
payment intent
  -> provider attempt
  -> verified provider result
  -> approved contribution confirmation
  -> approved ledger posting
  -> share creation
```

Each transition must have an explicit approved rule and idempotency boundary.
If the rules are not approved, record the open question and stop that part of
the implementation.

### 10. Security and privacy

Implement and test:

- Chairperson authorization for connection management.
- Active-membership checks on every Chama-scoped operation.
- No cross-Chama connection, intent, attempt, or event access.
- Secret redaction in logs, traces, exceptions, and validation errors.
- Request-body size limits on callbacks.
- Provider-specific signature/authentication checks.
- Replay prevention.
- Rate limits on credential validation, payment initiation, and callbacks.
- Safe timeouts and bounded retries.
- No credential values in OpenAPI examples.
- No raw provider payloads in ordinary application logs.
- Audit events for credential lifecycle and payment state changes.

Never ask a user to paste credentials into this conversation. The credential
input belongs in the application flow and must be encrypted immediately.

### 11. Operational behavior

Document:

- timeout values per provider,
- retryable versus non-retryable failures,
- idempotent versus non-idempotent operations,
- provider outage behavior,
- status polling behavior,
- callback retention,
- credential rotation,
- key rotation,
- dead-letter/manual review behavior,
- reconciliation procedure for ambiguous payments.

Use structured correlation IDs:

```text
chama_id
payment_intent_id
payment_attempt_id
connection_id
provider_request_id
provider_transaction_id
provider_event_id
```

These identifiers may be logged. Secrets and full payment payloads may not.

## API expectations

Design and document endpoints similar to:

```text
POST   /api/v1/chamas/{chama_id}/payment-connections
GET    /api/v1/chamas/{chama_id}/payment-connections
POST   /api/v1/chamas/{chama_id}/payment-connections/{id}/validate
PATCH  /api/v1/chamas/{chama_id}/payment-connections/{id}
POST   /api/v1/chamas/{chama_id}/payment-connections/{id}/disable

POST   /api/v1/chamas/{chama_id}/payment-intents
GET    /api/v1/chamas/{chama_id}/payment-intents/{id}
GET    /api/v1/chamas/{chama_id}/payment-attempts/{id}

POST   /api/v1/payments/webhooks/{provider_code}/{environment}
```

These are design targets, not permission to guess final API contracts.
Finalize them in `docs/06_API_CONTRACT.md` and an approved ADR first.

Credential responses must never contain:

- client secrets,
- consumer secrets,
- passkeys,
- access tokens,
- signing keys,
- encrypted credential blobs.

## Testing requirements

The normal test suite must include:

### Database and migration

- Fresh SQLite migration.
- Fresh PostgreSQL migration.
- Upgrade from the current V2 head.
- Downgrade behavior where supported.
- Alembic check.
- All provider/payment constraints.
- Concurrent uniqueness and idempotency tests.

### Credential security

- Chairperson can configure only their own Chama.
- Non-chairperson receives 403.
- Raw secrets never appear in responses, logs, errors, or repr output.
- Replacing credentials invalidates the old credential version.
- Disabling a connection blocks new attempts.
- Key rotation preserves decryptability.
- Wrong encryption key fails safely.

### Provider adapters

- Jenga unit tests with mocked HTTP.
- Jenga timeout, auth failure, malformed response, and retry tests.
- Daraja STK Push unit tests with mocked HTTP.
- Daraja callback parsing and status mapping tests.
- Provider contract tests independent of the business domain.
- Sandbox integration tests only when explicitly enabled.

### Payment lifecycle

- Duplicate payment-intent request.
- Same idempotency key with changed payload.
- Duplicate provider request.
- Duplicate callback.
- Out-of-order callback.
- Concurrent callbacks.
- Delayed callback with status query.
- Provider success, failure, timeout, and unknown states.
- Disabled connection during an in-flight attempt.
- No duplicate contribution confirmation.
- No duplicate ledger posting.

### Regression

- All existing V1 tests pass.
- All existing V2 tests pass.
- PostgreSQL CI runs without duplicate trigger setup.
- SQLite and PostgreSQL behavior remain aligned where SQLite supports the
  invariant.

## Scope restrictions

Do not implement yet:

- loans or repayments,
- payouts,
- bank reconciliation,
- notifications,
- frontend or mobile UI,
- USSD,
- microservices,
- arbitrary provider credentials in environment variables,
- automatic ledger/account mappings not approved in the ADRs,
- production Daraja until sandbox behavior is verified,
- provider-specific logic in the contribution or ledger services.

## Definition of done for the first V3 increment

The first V3 increment is complete only when:

1. The PostgreSQL trigger-test setup defect is fixed.
2. V1 and V2 tests pass on SQLite and PostgreSQL.
3. Payment-domain and provider-abstraction ADRs are approved.
4. Credential encryption and chairperson-only connection management are
   implemented and tested.
5. Jenga sandbox adapter and mocked contract tests pass.
6. Payment intent and attempt state machines are implemented.
7. Idempotency and callback deduplication are database-backed.
8. No raw credentials appear in any response, log, trace, or error.
9. The payment layer does not yet guess contribution-to-ledger rules.
10. Daraja STK Push is implemented only behind the same provider-neutral
    interface.
11. All migrations and `alembic check` pass.
12. The report names every remaining provider limitation and unresolved
    business rule.

Start with the documentation and PostgreSQL trigger fix. Then implement the
provider-neutral payment domain and credential lifecycle before adding the
Jenga adapter. Do not begin by embedding Jenga HTTP calls in the contribution
endpoint.