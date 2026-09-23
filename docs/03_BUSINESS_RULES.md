# Business Rules

Only rules marked `APPROVED` may be implemented.

## Approved rules

### Member and membership

- A Member represents a person.
- A Membership represents participation in one Chama.
- Contributions and shares reference Membership.
- Membership numbers are generated server-side.
- Membership numbers must not use `COUNT(*) + 1`.
- Membership numbers are unique within a Chama (`UNIQUE(chama_id, membership_number)`).
- A person cannot have duplicate membership in one Chama (`UNIQUE(chama_id, member_id)`).
- Membership numbers are allocated transactionally using a sequence table.

### Money

- Monetary values cannot be negative.
- Monetary values use `Decimal`.
- Database monetary columns use `NUMERIC`.
- Confirmed financial records cannot be silently deleted.

### Identity (ADR-007)

- Both `phone_number` and `government_id` are globally unique on the `members` table.
- Duplicate phone or government ID is rejected at creation time.

### User-to-member linking (ADR-008 addendum, OQ-008)

- A user not yet linked to a member may claim their identity by matching a
  member's `phone_number` and `government_id` through
  `POST /api/v1/auth/me/member-link`.
- A user already linked to a member cannot claim again.

### One User per Member (OQ-009)

- A Member identity may be linked to only one User account.
- A second account attempting to claim an already-linked member is rejected
  with `409 Conflict`.

### Government-ID exposure (OQ-010)

- Membership and Chama membership-list responses omit `government_id`.
- `government_id` is only returned via the authenticated user's own member
  data through the auth endpoints.

### JWT secret fail-closed (OQ-011)

- When `CHAMACORE_DEBUG=false` the application must reject startup unless
  `CHAMACORE_JWT_SECRET_KEY` is set to a non-default value.

### Chama access (ADR-008)

- The creator of a Chama is automatically added as a member with `CHAIRPERSON` role.
- Authorization requires an active membership in the Chama.

### Registration fees (ADR-003)

- Registration fee is copied from the Chama at membership creation as an obligation (`OWED`).
- Fee statuses are `OWED` or `WAIVED`.
- Registration fee rows are never physically deleted.

### Contributions (ADR-004, ADR-009)

- Contribution period is a calendar month in `YYYY-MM` format.
- Statuses are `PENDING`, `CONFIRMED`, `REVERSED`.
- Only `CHAIRPERSON` or `TREASURER` may record contributions.
- Only `CHAIRPERSON` may confirm or reverse contributions.
- `CONFIRMED` contributions are immutable in amount and period.
- Correction is recorded by changing status to `REVERSED` with an optional note.
- A membership may have at most one non-reversed contribution per period.
- Contribution rows are never physically deleted.

### Shares (ADR-005)

- Each confirmed contribution creates one share record.
- `units = amount / SHARE_UNIT_PRICE` (default KES 100).
- Shares are created automatically when a contribution is confirmed.
- Fractional units are permitted.
- Share records are never physically deleted.

### Roles (ADR-006)

- Four roles: `CHAIRPERSON`, `TREASURER`, `SECRETARY`, `MEMBER`.
- Every membership automatically receives `MEMBER`.
- `MEMBER` cannot be assigned or removed through the role API.
- A membership may hold at most one leadership role (`CHAIRPERSON`, `TREASURER`, or `SECRETARY`).
- A Chama may have at most one `CHAIRPERSON`.
- Only `CHAIRPERSON` may assign or remove leadership roles.
- `TREASURER` and `SECRETARY` have no role-assignment powers.
- `CHAIRPERSON` may confirm or reverse contributions.
- `CHAIRPERSON` or `TREASURER` may record contributions.
- `CHAIRPERSON` may waive registration fees.
- `CHAIRPERSON`, `TREASURER`, or `SECRETARY` may create memberships.
- Only `CHAIRPERSON` may update Chama details or Chama status.
- Only `CHAIRPERSON` may update a membership's status.

### Ledger double-entry (ADR-010, ADR-012)

- A financial transaction is a single balanced, immutable accounting event
  owned by one Chama and produced by one approved business event, recorded
  with its source reference and its debit/credit entries.
- Every entry carries either a debit or a credit; a transaction balances when
  total debits equal total credits.
- Accounts are Chama-scoped and typed: `ASSET`/`EXPENSE` debit normally,
  `LIABILITY`/`EQUITY`/`REVENUE` credit normally.
- Ledger transactions and entries are never updated or deleted; corrections
  are compensating transactions referencing the original (ADR-011).
- Posting is idempotent by `UNIQUE (source_type, source_id)`; a conflicting
  retry (different amount, accounts, description, or Chama) raises
  `ConflictError`.
- No public endpoint writes to the ledger; only the trusted posting service
  posts, after an approved business action (ADR-012, ADR-013).

### Default chart of accounts (OQ-012 / ADR-019)

- Each Chama is seeded with exactly three accounts, idempotently per
  `(chama_id, code)`: `1000` Cash (ASSET), `3000` Share Capital (EQUITY),
  `4000` Registration Fees (REVENUE). Further account creation is a future
  business decision.

### Contribution-to-ledger posting (ADR-014, OQ-013)

- Confirming a `PENDING` contribution posts one balanced transaction —
  debit `1000` Cash, credit `3000` Share Capital — idempotent by
  `CONTRIBUTION_CONFIRMATION:<contribution_id>`.
- Reversing a `CONFIRMED` contribution posts a compensating reversal
  (ADR-011). Reversal rules for other flows are pending their open questions.

### Money precision (ADR-013)

- All money is `Decimal` backed by `NUMERIC(18, 2)`, quantized to two decimal
  places with `ROUND_HALF_UP`. Floating-point is never used for money.

### Ledger authorization (ADR-013)

- Reading a Chama's ledger history, accounts, and account entries requires an
  active membership in that Chama (any role).
- Every ledger query is Chama-scoped; the composite FKs enforce ownership at
  the database level.

### C2B and STK settlement (ADR-019, OQ-021)

- The C2B Validation URL accepts (`ResultCode = 0`) only when `BillRefNumber`
  equals the membership number of an ACTIVE membership on an ACTIVE payment
  connection; everything else is rejected (`ResultCode = 1`).
- The C2B Confirmation URL stores the payment idempotently by `TransID`,
  records a confirmed contribution for the current `YYYY-MM` period, and posts
  the ledger entry as the system user. Duplicate deliveries are deduplicated:
  one contribution and one posting per `TransID`.
- A succeeded payment intent settles its linked contribution as the system
  user, idempotently. A succeeded intent without a linked contribution is a
  no-op; a duplicate success callback is an idempotent retry.
- Payout status is not equivalent to financial settlement; the payment domain
  distinguishes business state from provider/ledger outcome.

### Payments (ADR-016..ADR-018)

- Providers are adapters behind an internal port; business logic never depends
  on a provider directly. Only registered providers can be used (currently
  Daraja; Jenga code retained but unregistered).
- Payment connections are unique per `(chama, provider, environment)`;
  credentials are sealed with AES-256-GCM and never returned by any endpoint.
- Connection lifecycle is controlled: `PENDING_VALIDATION → ACTIVE | INVALID`,
  with replace and disable; delete is blocked when financial history exists.
- Payment intents are idempotent by `(chama_id, idempotency_key)` with payload
  hash matching; attempts are sequentially numbered, at most one in flight,
  and retried only after transient failures (known non-retryable errors are
  permanent).
- Callbacks enter a deduplicated, append-only inbox: duplicates are idempotent,
  payload conflicts and amount/currency mismatches are recorded as
  `DISAGREEMENT`.

### Authentication sessions (production-readiness brief 3.1)

- Access tokens are short-lived JWTs (default 120 minutes). Refresh tokens are
  opaque, stored only as SHA-256 digests, single-use, and rotate on exchange.
- Presenting a used, revoked, expired, or unknown refresh token fails with 401.
- The system posting account (`system@chamacore.invalid`) is a non-login
  account and is always rejected at login.

### Production API surface (brief 3.2, 3.3, 3.5)

- When `CHAMACORE_DEBUG=false`: interactive docs and the raw OpenAPI schema
  are disabled (404); `/metrics` requires `X-Metrics-Token` matching
  `CHAMACORE_METRICS_TOKEN` (404 without/on mismatch, and when the token is
  unset); production builds send `X-Content-Type-Options`, `Referrer-Policy`,
  and `Strict-Transport-Security` headers.

### Not approved (blocked)

No rule exists for registration-fee payment accounting (OQ-014), loan
eligibility/limits/interest/schedules (OQ-015..OQ-018), or payouts
(OQ-019..OQ-020). These rules must be decided and recorded in the ADRs before
any implementation. Unresolved decisions must not be guessed.
