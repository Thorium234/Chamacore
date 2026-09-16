# V2 — Financial Core — Design

Status: In progress. Version 2 (Financial Core) has started.

## Goal

V2 gives ChamaCore a provable financial core: a ledger that records every
approved financial event, financial transaction history, loans, loan
repayments, and payouts. The ledger is the source of truth; all money
movement is represented as balanced ledger entries.

## Scope (this increment)

This increment delivers the **ledger foundation**:

- The immutable double-entry ledger schema (ADR-010, ADR-011).
- Ledger accounts (ADR-012).
- The trusted posting service with idempotency (ADR-012).
- The financial transaction history read endpoint (ADR-013).
- Tests and migrations for the ledger.

Loans, repayments, and payouts are documented below but are **blocked** by
open questions and are not implemented.

## What a financial transaction is

A financial transaction is a single balanced, immutable accounting event
owned by one Chama, produced by one approved business event, recorded with
its source reference, its actor, and its debit/credit entries.

See ADR-010.

## Ledger immutability

The ledger is append-only. Transactions and entries are never updated or
deleted. Corrections are compensating transactions that invert the original
and reference it (`reverses_transaction_id`). See ADR-011.

## Debit/credit account types

Accounts are Chama-scoped and typed (ADR-012):

| Type | Normal side |
| --- | --- |
| `ASSET` | debit |
| `EXPENSE` | debit |
| `LIABILITY` | credit |
| `EQUITY` | credit |
| `REVENUE` | credit |

Each entry carries either a debit or a credit amount. A transaction balances
when total debits equal total credits. The default chart of accounts for a
new Chama is unresolved (OQ-012).

## How contributions post to the ledger

Proposed but **blocked**: a confirmed contribution posts one balanced
transaction; a reversed contribution posts a compensating transaction
(ADR-014). The concrete account mapping needs decisions OQ-012 and OQ-013.

## How shares relate to ledger entries

Unchanged from V1: shares are units derived from a confirmed contribution's
amount (`amount / SHARE_UNIT_PRICE`, ADR-005). Shares are a unit ledger
concept, not money movement.

The question of whether share records should also be represented as ledger
entries is part of the chart-of-accounts decision (OQ-012) and is not
decided.

## Loans, repayments, and payouts

All blocked. See open questions:

| Area | Open questions | Blocked work |
| --- | --- | --- |
| Loan eligibility | OQ-015 | loan creation |
| Loan principal limits | OQ-016 | loan creation |
| Interest / service charges | OQ-017 | repayment math, ledger postings |
| Repayment schedules | OQ-018 | schedules |
| Late payments / defaults | OQ-018 | late handling |
| Payout eligibility | OQ-019 | payout creation |
| Payout approval / authorization | OQ-020 | payout API and postings |

## Reversal and correction rules

Approved at the ledger level (ADR-011): compensating transactions only. The
business-level reversal rules (which events may reverse, and with what
postings) are pending the ledger connection decision (ADR-014) and the open
questions above.

## Idempotency requirements

Approved (ADR-012): `UNIQUE (source_type, source_id)` on ledger transactions.
Posting the same source twice returns the existing transaction without side
effects. This protects retries and duplicate events.

## Decimal precision and rounding

Approved (ADR-013): `Decimal` + `NUMERIC(18, 2)`, quantities quantized to
two decimal places with `ROUND_HALF_UP`. No floating-point money anywhere.

## Authorization

Approved (ADR-013):

- Reading a Chama's financial transaction history requires an active
  membership in that Chama (any role), matching V1 for contributions and
  shares.
- Posting requires a previously authorized business action; the posting
  service additionally requires active membership (defense in depth).
- No public endpoint writes to the ledger.
- Chama-scoping is enforced on every ledger query.

## Audit requirements for financial actions

Approved (ADR-013): every ledger transaction records the actor
(`posted_by_user_id`), timestamp, source reference, and (for corrections) the
reversed transaction. A general audit-event table for all sensitive V2
actions is planned separately.

## Database design

Three tables (migration delivered this increment):

```text
ledger_accounts       id, chama_id FK, code, name, account_type,
                      UNIQUE(chama_id, code), timestamps

ledger_transactions   id, chama_id FK, source_type, source_id,
                      describes business event, posted_by_user_id FK,
                      reverses_transaction_id FK (nullable),
                      UNIQUE(source_type, source_id), timestamps

ledger_entries        id, transaction_id FK, account_id FK,
                      debit NUMERIC(18,2) >= 0, credit NUMERIC(18,2) >= 0,
                      checks: one side positive, not both,
                      timestamps
```

The unique `(source_type, source_id)` and the side/absence checks are
database-level backstops for the service rules.

## API surface (this increment)

| Method | Path | Authorization | Status |
| --- | --- | --- | --- |
| `GET` | `/api/v1/chamas/{chama_id}/ledger` | active member | implement |

No posting, reversal, or account-management endpoints are exposed publicly.

## Implementation order

1. Design + ADRs (this document, ADR-010..ADR-014).
2. Ledger schema and posting service + tests + migration. **— this increment**
3. Verified: 66 V1 tests still pass; migrations apply on SQLite (and
   PostgreSQL in CI).
4. Connect confirmed contributions to the ledger — **blocked** by OQ-012 /
   OQ-013.
5. Loans and repayments — **blocked** by OQ-015..OQ-018.
6. Payouts — **blocked** by OQ-019 / OQ-020.
7. General audit events for sensitive financial actions — later.

## Explicitly marked unresolved

Recorded in `docs/decisions/OPEN_QUESTIONS.md` (OQ-012..OQ-020). No
unresolved business rule has been guessed.