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
Fees (REVENUE) — idempotently per `(chama_id, code)`. Existing Chamas are
backfilled by migration `f2b4d6a8e0c1`. Any further account creation remains a
future business decision. See ADR-019.

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

Connecting confirmed contributions to the ledger (OQ-012/OQ-013, resolved
above), registration-fee payments (OQ-014), and loan, repayment, and payout
flows (OQ-015..OQ-020) are the remaining V2 work and are not part of V3.

### OQ-021: C2B (Paybill) payment intake and STK settlement

Decision (2026-09-22): ADR-019. See also OQ-012/OQ-013 above, which the
decision builds on.

## Open (V2)

Phases 4 (financial reporting beyond the existing ledger balances/entries) and
6 (business audit events) of the scale report are considered in the section
below. OQ-014..OQ-020 are resolved by ADR-020..023; no V2 financial-domain open
questions remain.

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

## Open (backend completion spec — `reports/latestreport.md`)

`reports/latestreport.md` (CHAMACORE_BACKEND_COMPLETION_SPEC) requires the
financial domain below. Its Phase 1 rule is: missing financial rules must be
recorded here and decided, not guessed. The decisions the spec needs are the
same as OQ-014..OQ-020 above, plus the chart-of-accounts and report/audit/
notification/reconciliation definitions below. While any of these is OPEN,
the corresponding scale-report step and completion-spec phase stays blocked.

| # | Decision needed | Required by | Recommended default (pending ratification) |
| --- | --- | --- | --- |
| D-01 | Loan eligibility and principal limit | OQ-015/OQ-016, spec §7 | ACTIVE membership with ≥1 month tenure; principal ≤ 3× member share value AND ≤ available Chama cash (ledger-derived) — **ratified, ADR-020** |
| D-02 | Loan interest and repayment schedule | OQ-017/OQ-018, spec §7–§12 | Flat service interest 5% of principal; equal monthly installments over 3–12 months; no accrual before disbursement — **ratified, ADR-020** |
| D-03 | Repayment allocation order and overpayments | spec §12 | Allocate interest first, then principal; overpayments rejected with 400; no automatic late penalties — **ratified, ADR-020** |
| D-04 | Payout eligibility and approval | OQ-019/OQ-020, spec §13–§15 | Any ACTIVE member may request up to outstanding share value; CHAIRPERSON approves; requester cannot self-approve; completion posts DR membership equity / CR Cash — **ratified, ADR-021** |
| D-05 | Registration-fee payment accounting | OQ-014, spec §16 | Fee status gains `PAID`; payment posts DR Cash / CR `4000` Registration Fees (idempotent); waived fees post nothing; no backfill migration — **ratified, ADR-022** |
| D-06 | Loan/payout chart of accounts | OQ-012 ("further account creation is a future decision"), spec §10 | Add `1100` Loans Receivable (ASSET), `5000` Interest Income (REVENUE); payouts draw against `3000` Share Capital — **ratified, ADR-020** |
| D-07 | Report definitions | spec §17 | Chama summary + member summary + ledger statements derived from posted entries only; loan/payout report fields added once those modules exist |
| D-08 | Audit event scope | scale report step 9, spec §19–§21 | Record the spec §20 action list for existing operations as append-only events — **ratified, ADR-023** |
| D-09 | Notification scope and channels | spec §25–§27 | Backend notification records for the spec §25 events; channel delivery deferred; deterministic keys `type:{entity_id}:{recipient_id}` |
| D-10 | Reconciliation scope and matching | spec §22–§24 | Import statement rows; match against C2B/STK settlement records by amount+date+reference; states UNMATCHED/MATCHED/DISPUTED/RESOLVED/IGNORED; never writes the ledger directly |

Phases 2–4 and 6 of the completion spec (loans, repayments, payouts,
registration-fee settlement, and the business audit event system) are
implemented following decisions D-01..D-08, recorded as ADR-020..023. Reports
referencing the new keywords (D-07) follow phase 8. Notifications (D-09) and
reconciliation (D-10) override an earlier DEFERRED note in AGENTS.md and
therefore need explicit ratification.

## Guiding rule (AGENTS.md)

If a decision is missing:

1. Do not silently choose an implementation.
2. Record it in `docs/decisions/OPEN_QUESTIONS.md`.
3. Explain which work is blocked.
4. Ask for a decision.