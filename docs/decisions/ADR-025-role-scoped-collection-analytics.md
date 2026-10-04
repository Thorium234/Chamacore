# ADR-025: Role-scoped collection analytics

**Status:** Accepted  
**Date:** 2026-10-04

## Context

The dashboard needs useful collection trends without creating a second
financial source of truth or granting the global platform administrator
access to each Chama's member finances.

## Decision

- Expose the last twelve calendar months of net cash flow for posted
  contribution confirmations and registration-fee payments.
- Derive the values from the Chama's `1000` Cash ledger entries. Reversals
  reduce the month in which the reversal is posted.
- Return separate contribution and registration-fee series plus their monthly
  total. These are collections, not a claim that member contributions are
  accounting revenue.
- CHAIRPERSON, TREASURER, and SECRETARY receive Chama-wide series. Other active
  members receive only series tied to their own membership.
- A `PLATFORM_ADMIN` grant alone gives no access to Chama collection analytics.
  Platform analytics remain operational (Chama lifecycle and account/member
  counts).
- Do not include loan repayments, interest, payouts, or other sources in these
  collection series. Broader report definitions remain open under D-07.

## Consequences

The backend owns aggregation and authorization. The frontend only visualizes
the returned monthly values. Future subscription billing analytics require a
separate subscription-payment source and must not be inferred from Chama
collections.
