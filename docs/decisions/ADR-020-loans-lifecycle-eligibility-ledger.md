# ADR-020: Loan Lifecycle, Eligibility, and Ledger Integration

## Status

Approved 2026-09-23 (resolves OQ-015, OQ-016, OQ-017, OQ-018; decisions
D-01, D-02, D-03, and D-06 from `OPEN_QUESTIONS.md`).

Implemented 2026-09-23: services `app/services/loan.py`, models
`app/models/loan.py` and `loan_repayment.py`, repos, schemas, API router
`app/api/v1/loans.py`, migration `9a8b7c6d5e4f`, and `tests/test_loans.py`
and `tests/test_loan_repayments.py`.

## Context

`reports/latestreport.md` (CHAMACORE_BACKEND_COMPLETION_SPEC) requires a
complete backend loan lifecycle with ledger integration. The existing
repository records no loan eligibility, interest, or repayment rules, so
the domain decisions were recorded in `OPEN_QUESTIONS.md` (D-01..D-03,
D-06) and ratified by the product owner.

## Decision

### Lifecycle

A loan moves through controlled statuses, enforced in the service layer and
constrained in the database:

```text
DRAFT
    ↓
SUBMITTED
    ↓
APPROVED ──→ CANCELLED
    ↓
DISBURSED
    ↓
PARTIALLY_REPAID
    ↓
REPAID
```

Failure/rejection paths are SUBMITTED→REJECTED and APPROVED→CANCELLED.
Transitions are only allowed from the documented predecessor states.

### Eligibility and principal limit (D-01)

A member may apply when all of the following hold:

- the membership is `ACTIVE`;
- the membership has been joined for at least one month
  (`joined_at <= now - 30 days`);
- `principal <= 3 x share value` of the member, where share value is the sum
  of `ACTIVE` share units times the share unit price (ledger-independent,
  derived from confirmed contributions);
- `principal <=` the Chama's available cash, derived from the ledger `1000`
  Cash account balance (computed from posted entries on demand, never stored).

A member with zero share value has a zero limit and therefore cannot borrow
until they hold shares.

### Interest and schedule (D-02)

- Interest is a flat service charge of `5%` of principal, computed at
  disbursement and never accrued before it:
  `total_interest = principal * 0.05`, quantized to the cent.
- The term is chosen at application: a whole number of months from 3 to 12.
- Repayment is by equal monthly installments of
  `(principal + total_interest) / term_months`; members may repay early or
  partially at any time.
- `maturity_date` is set at disbursement to `disbursement_date` plus
  `term_months` calendar months. No automatic late penalties exist; a loan
  whose maturity date has passed with a positive outstanding balance is
  reported as overdue (derived, never stored).

### Repayment allocation (D-03)

Each repayment is allocated **interest first, then principal**:

```text
interest_portion  = min(amount, outstanding_interest)
principal_portion = amount - interest_portion
```

Repayments that exceed the total outstanding balance (principal plus
interest) are rejected with `400 INVALID_STATE`. There is no automatic late
penalty.

### Outstanding balances and no duplication

`outstanding_principal` and `outstanding_interest` are **derived on read**
from confirmed (non-reversed) repayment rows, never stored on the loan:

```text
outstanding_principal = principal - sum(principal_portion of CONFIRMED repayments)
outstanding_interest  = interest   - sum(interest_portion  of CONFIRMED repayments)
```

The same rule is enforced as the `Repaid amount <= repayment obligation`
invariant. A repayment reversal recomputes the loan status from the
remaining confirmed repayments.

### Chart of accounts (D-06)

Two accounts are added to the default chart of accounts, seeded for every
Chama (new Chamas in code, existing Chamas by data migration):

- `1100` Loans Receivable (ASSET)
- `5000` Interest Income (REVENUE)

### Ledger integration

| Event       | Ledger transaction (idempotency key `source_type:source_id`) |
| ----------- | ------------------------------------------------------------ |
| Disbursement | Debit `1100` Loans Receivable / Credit `1000` Cash · `LOAN_DISBURSEMENT:<loan_id>` |
| Repayment   | Debit `1000` Cash / Credit `1100` principal + Credit `5000` interest · `LOAN_REPAYMENT:<repayment_id>` |

Disbursement is atomic: the `APPROVED`→`DISBURSED` status change and the
ledger posting happen in one database transaction, so neither state can
exist without the other. Retrying disbursement is idempotent through the
ledger source uniqueness and an already-`DISBURSED` loan.

Repayment reversal posts the standard compensating reversal (ADR-011)
referencing the repayment posting; the repayment row is marked `REVERSED`.

### Authorization

- Apply: the member themselves (active membership, any role).
- Approve / reject / cancel / disburse: `CHAIRPERSON`. The applicant can
  never approve or reject their own loan (`actor` must differ from the
  applicant user).
- Record a repayment (money in): `CHAIRPERSON` or `TREASURER`.
- Reverse a repayment: `CHAIRPERSON`.

## Consequences

- Loans and repayments now exist as first-class financial records wired to
  the immutable ledger (ADR-011/ADR-012/ADR-013).
- OQ-015..OQ-018 are resolved; the scale-report steps "Loans" and "Loan
  repayments" and completion-spec Phase 2 are unblocked.
- Financial reports referencing loans (D-07) remain blocked only on the
  report-definition decision.