You are the implementation agent for ChamaCore.

First read:
- AGENTS.md
- docs/00_PROJECT_STATUS.md
- docs/01_PRODUCT_REQUIREMENTS.md
- docs/02_DOMAIN_MODEL.md
- docs/03_BUSINESS_RULES.md
- docs/04_DATABASE.md
- docs/05_ARCHITECTURE.md
- docs/06_API_CONTRACT.md
- docs/07_DEVELOPMENT_PROCESS.md
- docs/08_ROADMAP.md
- docs/13_TEST_INVENTORY.md
- docs/decisions/OPEN_QUESTIONS.md
- reports/CHAMACORE_SCALE_ENGINEERING_REPORT.md

Current truth: V1, the V2 financial core (including registration-fee
settlement, loans, repayments, and payouts), V3 Payments, the append-only
business audit event system, and production-readiness work are implemented.
The approved decisions are ADR-020..ADR-023. Follow `docs/08_ROADMAP.md` for
current scope; financial reporting beyond ledger reads remains blocked on D-07,
while notifications and reconciliation await ratified scope (D-09/D-10).

Do not reimplement completed modules or invent additional financial behavior.
For any unresolved decision, record the blocker and stop that portion of work.

Do not rewrite the ledger, payment flows, ORM, framework, or architecture.
Preserve the modular monolith and the API → schema → service → repository →
model layering. Prefer additive API changes; document breaking changes
explicitly.

Do not guess business rules. If any required decision is marked OPEN, report
the exact blocker and stop that part instead of inventing behavior.

Financial rules: use Decimal and NUMERIC for money, never floats; the ledger
is the authoritative financial record; financial side effects must be
idempotent and DB-protected; corrections are compensating transactions; never
silently delete confirmed financial records.

Every feature requires tests (authorization, duplicates, concurrency, invalid
amounts, status transitions, rollback, historical-record protection) and is
complete only when its approved rule, migration, API contract, tests, and
documentation agree (scale report §29). Never delete failing tests and never
add skips without recording a reason and activation path in
`docs/13_TEST_INVENTORY.md`. Update the documentation and project status after
each completed feature.
