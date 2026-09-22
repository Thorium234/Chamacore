# ADR-019: C2B Paybill Intake, Contribution Settlement, and STK Settlement

## Status

Approved 2026-09-22 (resolves OQ-021; builds on OQ-012/OQ-013 resolutions)

## Context

The M-Pesa Integration Validation Report (approved `2026-09-17`) requires a
C2B API: a Validation URL, a Confirmation URL, and a Register-URL activation
step. ADR-016 introduced the provider-port boundary and ADR-018 the webhook
inbox. This ADR records how a manual Paybill payment is matched to a Chama and
member, how its confirmation creates a contribution and ledger posting, and
how an STK push whose payment intent succeeds settles an associated
contribution.

## Decision

### C2B validation (Validation URL)

- The callback URL is the Chama's connection callback URL (ADR-017), guarded
  by the canonical payload hash (ADR-018).
- `BillRefNumber` must be exactly the server-assigned membership number
  (`memberships.membership_number`), formatted as its decimal string. It is
  never a phone number or free-form reference.
- Resolution is per Chama/connection: the connection's shortcode serves its
  own Chama. Resolve by Chama, then look up the membership by
  `(chama_id, membership_number)`.
- The transaction is accepted only if the connection is ACTIVE and the
  membership is ACTIVE. Otherwise the callback returns `ResultCode` 1 (service
  temporarily unavailable) semantics per provider M-Pesa contract and stores a
  `REJECTED`/`PROCESSED` outcome event accordingly.
- The external-facing shortcode must match the connection's configured
  shortcode; a `UNPROCESSABLE` outcome is recorded when the amount is not a
  positive number or the shortcode does not match.

### C2B confirmation (Confirmation URL)

- Confirmation is idempotent by `TransID`: a re-delivered confirmation for an
  already-processed `TransID` is deduplicated (no duplicate contribution, no
  duplicate ledger posting).
- On first confirmation, a contribution is created (or reused) for the
  membership for the current contribution period (`YYYY-MM`, ADR-004) with
  amount equal to `TransAmount`.
- The contribution is settled exactly once using the OQ-013 ledger posting
  (DR `1000` Cash / CR `3000` Share Capital), idempotent by source
  `CONTRIBUTION_CONFIRMATION:<contribution_id>`. The confirmation may run
  before validation (scenario where the provider skips the validation call):
  it resolves the membership the same way and records a `DISAGREEMENT`/
  `UNPROCESSABLE` outcome when the reference cannot be resolved or the amount
  differs from an existing `PENDING` contribution.
- Settlement of a manually-confirmed C2B contribution runs as the seeded
  system user (ADR-014), never as a caller-supplied identity.

### STK push settlement

- When a payment intent that was created against a contribution
  (`contribution_id`) reaches `SUCCEEDED` (either from a provider status query
  result or a webhook inbox event), the linked contribution is settled:
  same idempotent ledger posting, also as the system user.
- A settled contribution is refund-safe: reversal of the contribution posts a
  compensating ledger reversal per ADR-011/ADR-014.

## Consequences

- Manual Paybill payments and STK pushes now create contributions for the
  current period and post to the ledger. The V3 separation is preserved: the
  payment providers (Jenga, Daraja) and the webhook inbox still never touch
  contribution or ledger records directly; settlement goes through the
  contribution service.
- Idempotency is layered: `TransID` for C2B confirmation, source
  `CONTRIBUTION_CONFIRMATION:<id>` for ledger posting, and contribution status
  checks for settlement. Double-delivered callbacks are safe.
- No new business rules are invented for loans, payouts, or fee payments;
  OQ-014..OQ-020 remain open.