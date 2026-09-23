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

Current truth: V1 (Chama Foundation), the non-decision-blocked V2 Financial
Core, V3 Payments, and production readiness are implemented and tested. The
governing development brief is `reports/CHAMACORE_SCALE_ENGINEERING_REPORT.md`
and its order of work has been defined in AGENTS.md and `docs/08_ROADMAP.md`.

Do not implement loans, loan repayments, payouts, registration-fee ledger
payments, financial reporting beyond the existing ledger balances/entries, or
the business audit trail: each is blocked by an open question or an
undecided design (OQ-014..OQ-020), never guess those rules.

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