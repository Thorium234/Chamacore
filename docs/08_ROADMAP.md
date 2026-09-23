# ChamaCore Roadmap

## Governance

`reports/CHAMACORE_SCALE_ENGINEERING_REPORT.md` is the governing development
brief. Its development order is: repository consistency, deferred-test
inventory, financial domain decisions, registration-fee accounting, loans,
loan repayments, payouts, financial reporting, business audit trail, security
hardening, integration testing, performance measurement.

Sections below use the status labels `COMPLETED`, `CURRENT`, `NEXT`,
`DEFERRED`, and `OUT OF SCOPE`.

## COMPLETED

### V1 — Chama Foundation

- Users, chamas, members, memberships, roles, registration fees,
  contributions, shares
- Authentication, authorization, transactional membership numbers
- Migrations, automated tests, V1 hardening (identity-claim uniqueness,
  DB constraint backstops, government-ID masking, JWT secret fail-closed,
  health/readiness)

### V2 — Financial Core (non-decision-blocked parts)

- Immutable double-entry ledger + enforcement hardening (ADR-010..015)
- Financial transaction history with cursor pagination
- Chart-of-accounts seeding per Chama (OQ-012/ADR-019)
- Contribution confirmation/reversal ledger posting (ADR-014)
- C2B Paybill intake, contribution settlement, STK settlement (OQ-021/ADR-019)
- Read-only ledger account balances and per-account entries
- Round-trip money handling: `Decimal`, `NUMERIC(18,2)`, quantization

### V3 — Payment Architecture

- Provider port, registry, Daraja adapter (ADR-016); Jenga retained but
  unregistered
- Payment connection lifecycle with AES-GCM sealed credentials (ADR-017)
- Payment intent/attempt state machines
- Deduplicated append-only webhook inbox (ADR-018)
- Payment connections/intents/attempts API

### Production readiness

- Short-lived access tokens (120 minutes) with rotating single-use refresh
  flow and logout (brief `reports/ChamaCore_Developer_Implementation_Brief.md`)
- Interactive docs/OpenAPI disabled in production; `/metrics` protected by
  `CHAMACORE_METRICS_TOKEN`; production security headers
- System posting account login guard, production runbook, Docker Compose

## CURRENT

Step 1 (repository consistency) and Step 2 (deferred-test inventory) of the
scale report are complete as of `2026-09-23`. No feature code is in progress.

## NEXT (decision-blocked)

Steps 4–9 of the scale report cannot start until their open questions are
answered in `docs/decisions/OPEN_QUESTIONS.md`. Do not guess them.

| Area | Blocked by | Status |
| --- | --- | --- |
| Registration-fee ledger payments | OQ-014 | blocked |
| Loans | OQ-015..OQ-018 | blocked |
| Loan repayments | OQ-015..OQ-018 | blocked |
| Payouts | OQ-019 / OQ-020 | blocked |
| Financial reporting beyond existing balances/entries | report definitions | blocked |
| Business audit events | which sensitive actions to record | blocked |

When a decision is recorded, it must land as an ADR in `docs/decisions/` and
the corresponding scale-report step becomes the current work.

## DEFERRED

- Jenga as an active provider (code and contract tests retained; see
  `docs/13_TEST_INVENTORY.md`)
- Live provider sandbox integration tests (needs test credentials)
- Notifications, bank reconciliation, USSD, frontend, background workers

## OUT OF SCOPE

- Microservices, Kubernetes, Kafka, distributed databases, event sourcing /
  CQRS as replacements, Redis everywhere
- Rewriting the ledger, payment flows, ORM, or framework
- Extra payment providers without a documented requirement

## Must not change

- The modular monolith and its API → schema → service → repository → model
  layering (scale report §18–19)
- The ledger as the authoritative financial record (scale report §4)
- Existing financial API semantics (additive changes only, scale report §21)
- Historical ADRs and the migration history (scale report §3, §20)

## Scope rule

Only the current version in this roadmap plus the governing development brief
may be implemented. Business rules not yet approved are recorded as open
questions and must not be guessed. Implement only the current version in
`docs/08_ROADMAP.md`.