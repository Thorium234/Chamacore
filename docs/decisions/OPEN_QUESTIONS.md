# Open Questions

## Resolved

### OQ-001: Registration fee lifecycle

Decision: ADR-003 — Copy from Chama as OWED at membership creation.

### OQ-002: Contribution period

Decision: ADR-004 — Calendar month `YYYY-MM` string.

### OQ-003: Share formula

Decision: ADR-005 — `units = amount / SHARE_UNIT_PRICE` per contribution.

### OQ-004: Role rules

Decision: ADR-006 — Default MEMBER; up to one leadership role per
membership; one CHAIRPERSON per Chama; CHAIRPERSON manages all roles.

### OQ-005: Identity uniqueness

Decision: ADR-007 — Phone and government ID globally unique.

### OQ-006: Chama access model

Decision: ADR-008 — Creator becomes member + chairperson.

### OQ-007: Contribution statuses

Decision: ADR-009 — PENDING/CONFIRMED/REVERSED; no physical deletion.

### OQ-008: User-to-member identity linking

Decision: ADR-008 addendum — `POST /api/v1/auth/me/member-link` claims an
existing member matching the user's supplied `phone_number` and
`government_id`.

### OQ-009: Multiple accounts for one Member (P0 security fix)

Decision: One Member may be linked to only one User account. Enforced with
`UNIQUE (users.member_id)` and a `409` when a second account attempts to
claim an already-claimed member.

### OQ-010: Government-ID exposure

Decision: Chama/membership views return members without `government_id`
(public member schema). Full government IDs are only available to the user
whose own member record they belong to via the auth endpoints.

### OQ-011: JWT secret fail-closed

Decision: Outside development mode (`CHAMACORE_DEBUG=false`),
`CHAMACORE_JWT_SECRET_KEY` must be set; the known default secret is rejected
at configuration load.

### OQ-012: Chama chart of accounts — creation and maintenance

Decision (2026-09-22): On Chama creation, seed exactly three ledger accounts —
`1000` Cash (ASSET), `3000` Share Capital (EQUITY), and `4000` Registration
Fees (REVENUE) — idempotently per `(chama_id, code)`. Existing Chamas were
backfilled by migration `f2b4d6a8e0c1`. This initial chart was extended by
ADR-020 on 2026-09-23 with `1100` Loans Receivable (ASSET) and `5000` Interest
Income (REVENUE). The current default chart contains exactly these five
accounts; adding further accounts requires a future business decision.

### OQ-013: Contribution posting accounts

Decision (2026-09-22): Confirming a `PENDING` contribution posts one balanced
ledger transaction — debit `1000` Cash, credit `3000` Share Capital, for the
full amount — idempotent by `CONTRIBUTION_CONFIRMATION:<contribution_id>`.
Reversing a `CONFIRMED` contribution posts a compensating reversal (ADR-011).
See ADR-014 (now approved) and ADR-019.

### OQ-014 through OQ-020: V2 loans and payouts

Decision (2026-09-23): ADR-020 (loans and repayments), ADR-021 (payouts),
ADR-022 (registration-fee payment settlement), ADR-023 (business audit event
system). OQ-014 is resolved by ADR-022; OQ-015..OQ-018 by ADR-020; OQ-019 and
OQ-020 by ADR-021. See also `docs/10_V2_FINANCIAL_CORE.md` and
`reports/CHAMACORE_SCALE_ENGINEERING_REPORT.md` steps 4–7.

## Resolved (V3)

### V3 payment architecture

Decision: ADR-016 (provider port and adapters), ADR-017 (connection
lifecycle), ADR-018 (webhook inbox and event deduplication).

V3 delivers a provider-port boundary (Jenga and Daraja adapters), sealed
payment connections with a chairperson-controlled lifecycle, a payment
intent/attempt state machine, and a deduplicated, append-only webhook inbox.
All decisions are recorded in the three ADRs above; no V3 payment open
questions remain.

Connecting confirmed contributions to the ledger (OQ-012/OQ-013),
registration-fee payments (OQ-014), and loan, repayment, and payout flows
(OQ-015..OQ-020) are V2 financial workflows and are separate from V3 payment
provider architecture. They are implemented under ADR-014, ADR-019, and
ADR-020..ADR-022.

### OQ-021: C2B (Paybill) payment intake and STK settlement

Decision (2026-09-22): ADR-019. See also OQ-012/OQ-013 above, which the
decision builds on.

## V2 financial decisions — resolved

OQ-014..OQ-020 and business audit scope D-08 are resolved by ADR-020..ADR-023.
The remaining open items are financial-report definitions (D-07), notification
scope (D-09), and reconciliation scope (D-10). These are not authorization to
implement guessed behavior.

### OQ-014: Registration-fee payments and the ledger

Resolved (2026-09-23): ADR-022 — a fee payment is a recorded financial action.
`DR` Cash, `CR` `4000` Registration Fees, one row per fee status `PAID`,
idempotent by the partial-unique index on confirmed payments. Reversal returns
the fee to `OWED` with a compensating ledger transaction.

### OQ-015: Loan eligibility

Resolved (2026-09-23): ADR-020 — ACTIVE membership with at least 30 days
tenure; principal limited as in OQ-016. Eligibility is re-checked at
disbursement.

### OQ-016: Loan principal limits

Resolved (2026-09-23): ADR-020 — principal ≤ 3× the member's share value
(derived on demand from ACTIVE shares) AND ≤ available Chama cash (derived
from the ledger Cash account).

### OQ-017: Interest or service-charge rules

Resolved (2026-09-23): ADR-020 — flat service interest of 5% of principal
posted to `5000` Interest Income at repayment time (no accrual before
disbursement). Term 3–12 months.

### OQ-018: Repayment schedules, late payments, and defaults

Resolved (2026-09-23): ADR-020 — monthly maturity date derived from the calendar
at disbursement; repayments allocate interest first then principal; overpayments
are rejected; a maturity date past due is flagged `is_overdue` (read-only); no
late penalties or default statuses.

### OQ-019: Payout eligibility

Resolved (2026-09-23): ADR-021 — any ACTIVE member may request a payout up to
their outstanding share value (share value minus previously completed payouts)
and up to available Chama cash.

### OQ-020: Payout approval and authorization

Resolved (2026-09-23): ADR-021 — CHAIRPERSON approves; the requester cannot
self-approve; TREASURER/CHAIRPERSON process/complete; completion posts `DR`
`3000` Share Capital, `CR` Cash; a COMPLETED payout can be reversed with a
compensating entry; APPROVED payouts can be rejected; PROCESSING payouts can
fail.

## Remaining open decisions

`reports/latestreport.md` (CHAMACORE_BACKEND_COMPLETION_SPEC) contains the
original planned work. Financial-domain decisions D-01..D-06 and audit scope
D-08 have since been ratified in ADR-020..ADR-023. Only D-07, D-09, and D-10
remain open; their corresponding work stays blocked until decided.

| # | Decision | Required by | Current disposition |
| --- | --- | --- | --- |
| D-01 | Loan eligibility and principal limit | OQ-015/OQ-016, spec §7 | Ratified and implemented — ADR-020 |
| D-02 | Loan interest and repayment schedule | OQ-017/OQ-018, spec §7–§12 | Ratified and implemented — ADR-020 |
| D-03 | Repayment allocation and overpayments | spec §12 | Ratified and implemented — ADR-020 |
| D-04 | Payout eligibility and approval | OQ-019/OQ-020, spec §13–§15 | Ratified and implemented — ADR-021 |
| D-05 | Registration-fee payment accounting | OQ-014, spec §16 | Ratified and implemented — ADR-022 |
| D-06 | Loan/payout chart of accounts | OQ-012, spec §10 | Ratified and implemented — ADR-020 |
| D-07 | Report definitions | spec §17 | Partially resolved by ADR-025 for monthly net contributions and registration-fee collections; all other financial reports remain open |
| D-08 | Audit event scope | scale report step 9, spec §19–§21 | Ratified and implemented — ADR-023 |
| D-09 | Notification scope and channels | spec §25–§27 | Open; do not implement until ratified |
| D-10 | Reconciliation scope and matching | spec §22–§24 | Open; do not implement until ratified |

Phases 2–4 and 6 of the completion spec (loans, repayments, payouts,
registration-fee settlement, and business audit events) are implemented under
ADR-020..ADR-023. Phase 8 reporting remains blocked by D-07. Notifications
(D-09) and reconciliation (D-10) remain deferred until ratified.

## Strategic plan decisions (docs/15_STRATEGIC_PLAN.md)

The strategic plan (`docs/15_STRATEGIC_PLAN.md`) was implemented only where
the plan specifies a concrete rule. The deferred-test inventory (step 2) and
repo consistency (step 1) pages are unaffected. Implemented decision-free
items: **B1/W0** contribution list filters (`membership_id`, `period`,
`status`), chama-wide shares list (`GET /chamas/{chama_id}/shares`), and
**W4** canonical `2547…` member phone normalization (`app/core/phone.py`,
applied on member write/lookup and shared with the Daraja STK adapter).

| # | Decision | Required by | Current disposition |
| --- | --- | --- | --- |
| SP-1 | W1 identity schema: keep `users.email` nullable or add a `login_identifiers` table; login by email/phone/national ID | W1 auth | Open; do not guess the identity model |
| SP-2 | W1 password policy thresholds (min length, complexity classes, common-password blocklist) and OTP config (TTL, single-use scope, delivery port) | W1 auth | Open; plan names the features but not the values |
| SP-3 | W2 platform chama lifecycle: status states ("e.g."), reactivation rules, and the "operations only when ACTIVE / read-only when ON_HOLD" gating policy | W2 platform lifecycle | Open; plan states are examples ("e.g.") |
| SP-4 | W2 platform-admin role: system-level role/auth mechanism, list/PATCH admin APIs | W2 platform lifecycle | Open; platform admin is not a Chama role |
| SP-5 | W3 membership status transitions beyond ACTIVE/INACTIVE (ON_HOLD/TERMINATED), central permission matrix refactor, and manual-contribution `date` field semantics | W3 authz + CRUD | Open; new statuses contradict ADR-001 status set |
| SP-6 | W4 explicit `payer_phone` on STK initiate ("if allowed") — who may override the intent phone | W4/W5 (B5) | Open; plan says "if allowed" without a rule |
| SP-7 | W5 notifications: adopting the plan ratifies roadmap D-09 scope; schedule semantics (frequency/due day/amount) and outbox template/status enums still need approval | W5 (B7) | Open; aligns with roadmap deferred D-09 |
| SP-8 | W6 statements PDF: aggregation/date-range rules, format, delivery (file vs signed URL) | W6 (B8) | Open; no report definitions approved |
| SP-9 | W7 media: storage backend (object storage vs local disk), image constraints, URL signing | W7 (B8) | Open; no storage decision recorded |

Each phase that depends on an SP decision stays blocked until the decision is
ratified (AGENTS.md "No guessing").

## Guiding rule (AGENTS.md)

If a decision is missing:

1. Do not silently choose an implementation.
2. Record it in `docs/decisions/OPEN_QUESTIONS.md`.
3. Explain which work is blocked.
4. Ask for a decision.
