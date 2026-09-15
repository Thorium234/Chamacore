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
- docs/decisions/OPEN_QUESTIONS.md

Current truth: V1 (Chama Foundation) is implemented, tested (59 tests), and pushed. Future versions are out of scope.

Implement only V1:
Users, Chamas, Members, Memberships, Roles, Registration Fees, Contributions, Shares, authentication, authorization, migrations, and tests.

Do not implement loans, payments, M-Pesa, banks, payment providers, ledger, frontend, mobile, or USSD.

Do not guess business rules. If any required decision is marked OPEN, report the exact blocker and stop that part instead of inventing behavior.

When all required decisions are approved, implement in this order:

1. Application structure
2. Configuration and database sessions
3. SQLAlchemy V1 models
4. Alembic migrations
5. Authentication and authorization
6. Chama and membership APIs
7. Safe transactional membership-number generation
8. Roles and permissions
9. Registration fees
10. Contributions
11. Shares
12. Automated tests

Use Decimal and NUMERIC for money, UUID identifiers, database constraints, service/repository layers, and versioned APIs. Update the documentation and project status after each completed feature.
