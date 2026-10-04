# ChamaCore Roadmap

## Governance

This roadmap is the current implementation-status source of truth. The
engineering principles and recommended sequence are in
`reports/CHAMACORE_SCALE_ENGINEERING_REPORT.md`; its older sections describe
the work as it was planned before ADR-020..ADR-023. Those approved ADRs and
this roadmap supersede any earlier statements that the financial modules
remain blocked.

Only approved business rules may be implemented. Do not guess missing rules.

## COMPLETED

### V1 — Chama Foundation

- Users, Chamas, members, memberships, roles, registration-fee obligations,
  contributions, and shares.
- Role-scoped read access for member financial records, with executive group
  views and member-owned views (ADR-024).
- Authentication, authorization, transactional membership numbers,
  migrations, and V1 hardening (identity-claim uniqueness, database
  constraint backstops, government-ID masking, JWT secret fail-closed,
  health/readiness).
- Global platform administration, cross-Chama lifecycle controls, and
  operational dashboard metrics. First-admin provisioning is sourced from
  ignored runtime secrets by Alembic, with an idempotent CLI fallback.

### V2 — Financial Core

- Immutable double-entry ledger, enforcement hardening, and cursor-paginated
  financial transaction history (ADR-010..ADR-015).
- Per-Chama chart of accounts: `1000` Cash, `3000` Share Capital, `4000`
  Registration Fees, `1100` Loans Receivable, and `5000` Interest Income
  (ADR-019, ADR-020).
- Contribution confirmation and reversal posting (ADR-014).
- Registration-fee payment and reversal (ADR-022).
- Loan lifecycle, ledger-backed disbursement, repayments and compensating
  repayment reversal (ADR-020).
- Payout lifecycle, ledger-backed completion and compensating reversal
  (ADR-021).
- C2B Paybill and successful STK contribution settlement (ADR-019).
- Read-only account balances and account entries derived from posted ledger
  entries.
- Twelve-month net contribution and registration-fee collection analytics,
  derived from the ledger and scoped by member/executive role (ADR-025).
- Append-only business audit events for the approved sensitive-action scope
  (ADR-023).
- Decimal-safe money handling using `Decimal` and `NUMERIC(18,2)`.

### V3 — Payment Architecture

- Provider port and registry with Daraja active; Jenga code retained but
  unregistered (ADR-016).
- Payment connection lifecycle with sealed credentials (ADR-017).
- Payment intent/attempt state machines and an append-only deduplicated
  webhook inbox (ADR-018).
- Payment connections, intents, attempts, STK, and C2B APIs.

### Production readiness delivered

- Short-lived access tokens with rotating single-use refresh tokens and
  logout revocation.
- Interactive API docs/OpenAPI disabled in production; `/metrics` protected
  by `CHAMACORE_METRICS_TOKEN`; production security headers.
- System posting account login guard, structured request-correlated logs,
  rate limiting, production runbook, Dockerfile, and Docker Compose support.

## CURRENT

Documentation reconciliation for ADR-020..ADR-023 was completed on
2026-09-30. Keep the API contract, business rules, database/architecture
specifications, README, and status aligned with future implementation changes.
No financial behavior is changed by that documentation work.

## NEXT

| Area | Status | Reference |
| --- | --- | --- |
| Financial reporting beyond the role-scoped monthly collection series, ledger history, balances, and account entries | Blocked pending remaining definitions | D-07 in `docs/decisions/OPEN_QUESTIONS.md` |
| Notifications | Deferred; scope requires ratification | D-09 |
| Bank reconciliation | Deferred; scope requires ratification | D-10 |
| Targeted security hardening | Not started | Scale report, step 10 |
| Broader PostgreSQL/provider integration testing | Follow-up; live provider tests need credentials | Scale report, step 11; `docs/13_TEST_INVENTORY.md` |
| Performance measurement | Not started | Scale report, step 12 |

OQ-014..OQ-020 are resolved by ADR-020..ADR-022. D-08 audit scope is
implemented by ADR-023. Do not describe those areas as blocked.

## DEFERRED

- Activating Jenga as a provider; adapter code and contract tests are retained
  but outside current provider scope (`docs/13_TEST_INVENTORY.md`).
- Live Daraja/Jenga sandbox verification that requires provider credentials.
- Notifications, bank reconciliation, and USSD until their scope is approved.

## OUT OF SCOPE

- Frontend implementation in this backend repository (the consumer UI lives
  in the separate `frontend/chamacore-frontend` repository).
- Microservices, Kubernetes, Kafka, distributed databases, event sourcing or
  CQRS as replacements, Redis everywhere, or rewriting the ledger, ORM, or
  framework without a concrete approved requirement.
- Additional payment providers without a documented requirement.

## Must preserve

- The modular monolith and API → schema → service → repository → model layers.
- The ledger as the authoritative financial record.
- Existing financial API semantics; prefer additive changes.
- Historical ADRs and migration history.

## Scope rule

Implement only approved and current work in this roadmap. If a business rule
is missing, record the open question, identify the blocked work, and wait for
the decision instead of guessing.
