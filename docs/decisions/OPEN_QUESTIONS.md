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

## Open (V2)

### OQ-012: Chama chart of accounts — creation and maintenance

**Question.** When a Chama is created, what accounts should its ledger
receive, and how are accounts created/maintained afterwards?

**Blocked work.** Seeding `ledger_accounts` at Chama creation; any default
chart of accounts. The ledger tables and posting machinery exist, but no
account records are created automatically.

**Why it is open.** The composition of a chart of accounts is a business
decision (which asset, liability, equity, revenue, and expense accounts a
Chama needs), not an accounting-technical one that ChamaCore can derive.

### OQ-013: Contribution posting accounts

**Question.** When a confirmed contribution is posted to the ledger, which
accounts are debited and credited?

**Blocked work.** Step 4 of the V2 implementation order: connecting confirmed
contributions to ledger entries. ADR-014 is proposed but on hold.

**Why it is open.** Without a decision on the chart of accounts (OQ-012) and
the account mapping for a contribution, posting would invent a business rule.

### OQ-014: Registration-fee payments and the ledger

**Question.** V1 registration fees are OWED or WAIVED; there is no payment
flow. Should a fee payment be a recorded financial action on the ledger, and
if so, through which accounts and statuses?

**Blocked work.** Any registration-fee payment feature or posting rule.

**Why it is open.** No approved rule describes how fee money enters the
system.

### OQ-015: Loan eligibility

**Question.** Which memberships are eligible to borrow, and under what
conditions (e.g. active membership, minimum tenure, shares held, previous
defaults)?

**Blocked work.** Loan creation and all loan features.

### OQ-016: Loan principal limits

**Question.** What is the maximum loan principal a member can borrow, and how
is it calculated (e.g. multiple of shares, fixed amount, Chama fund balance)?

**Blocked work.** Loan creation.

### OQ-017: Interest or service-charge rules

**Question.** Are loans interest-bearing or service-charged? What rate or
formula applies, and how is it accrued and recorded on the ledger?

**Blocked work.** Loan interest and repayment amount calculation.

### OQ-018: Repayment schedules, late payments, and defaults

**Question.** What repayment schedule models are allowed (monthly, lump sum,
custom)? What happens on a late payment, and what constitutes a default?

**Blocked work.** Repayment schedules, late fees, default handling, and their
ledger postings.

### OQ-019: Payout eligibility

**Question.** Which members are eligible for a payout, what can be paid out
(e.g. share value, savings pool) and how is the amount calculated?

**Blocked work.** Payout creation.

### OQ-020: Payout approval and authorization

**Question.** Who may initiate and who must approve a payout, and is a payout
ever reversible?

**Blocked work.** Payout API and ledger posting.

## Guiding rule (AGENTS.md)

If a decision is missing:

1. Do not silently choose an implementation.
2. Record it in `docs/decisions/OPEN_QUESTIONS.md`.
3. Explain which work is blocked.
4. Ask for a decision.