# ChamaCore Roadmap

## Current version: V2 (in progress)

### V1 — Chama Foundation (complete)

- Users
- Chamas
- Members
- Memberships
- Roles
- Registration fees
- Contributions
- Shares
- Authentication
- Authorization
- Database migrations
- Automated tests

## V2 — Financial Core (current)

- Ledger (immutable double-entry, ADR-010..ADR-013) — foundation implemented
- Financial transaction history — implemented
- Chart of accounts seeding per Chama (OQ-012 / ADR-019) — implemented
- Contribution posting and reversal (ADR-014) — implemented
- C2B Paybill intake and contribution/STK settlement (ADR-019) — implemented
- Loans
- Loan repayments
- Payouts

Design and approved decisions: `docs/10_V2_FINANCIAL_CORE.md` and
`docs/decisions/`. OQ-012/OQ-013/OQ-021 are resolved (ADR-014, ADR-019).
Registration-fee payments (OQ-014), loans, repayments, and payouts are blocked
by open questions (OQ-014..OQ-020).

## V3 — Payment Architecture

- Payments
- Payment attempts
- Provider transactions
- Provider callbacks
- Provider interface
- Provider resolver
- Idempotency

## V4 and later — External providers

- Jenga
- Daraja
- KCB BUNI
- NCBA
- Bank integrations
- Reconciliation

## Later product versions

- Reports
- Audit
- Notifications
- React web application
- React Native application
- USSD
- Production hardening

## Scope rule

Only the current version (V2 Financial Core) may be implemented now.
Future versions describe direction, not current requirements. Business rules
not yet approved are recorded as open questions and must not be guessed.