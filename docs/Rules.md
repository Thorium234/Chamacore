ChamaCore Engineering Rules

«This document defines the engineering rules for everyone contributing to ChamaCore.

These rules exist to keep the codebase understandable, secure, testable, and maintainable as the team grows.»

---

1. Project Mission

ChamaCore is a production-oriented Chama management and financial platform.

The system will eventually handle:

- Chama management
- Members and memberships
- Roles and permissions
- Registration fees
- Contributions
- Shares
- Loans
- Loan repayments
- Payouts
- Financial ledger
- M-Pesa and other payment providers
- Bank accounts and transactions
- Reconciliation
- Reports and statements
- Notifications
- Web
- Mobile
- USSD

Because this is a financial system, correctness takes priority over development speed.

---

2. Core Engineering Principles

Rule 1 — Understand Before Coding

Do not immediately start writing code when assigned a feature.

First understand:

1. What problem are we solving?
2. What are the business rules?
3. Who is affected?
4. What data is involved?
5. What existing modules are affected?
6. What API changes are required?
7. What can go wrong?
8. How will the feature be tested?

If the requirements are unclear, ask before implementing.

---

Rule 2 — One Source of Truth

Every important concept must have one authoritative representation.

Do not create multiple competing representations of the same business state.

For example:

Contribution
Payment
ProviderTransaction
LedgerEntry

are different concepts.

Do not collapse them into one generic "Transaction" object simply because it appears convenient.

---

Rule 3 — Do Not Invent Business Rules

Developers must not silently invent financial or business behavior.

For example, do not decide yourself:

- How shares are calculated
- When a contribution becomes valid
- How loan interest works
- When a member becomes eligible for a loan
- How repayments are allocated
- How registration fees are treated
- How failed payments affect balances

If the rule is not defined, stop and clarify it.

---

3. Architecture Rules

Rule 4 — Current Architecture Is a Modular Monolith

The initial backend architecture is:

FastAPI
   │
   ├── Chama Domain
   ├── Member Domain
   ├── Contribution Domain
   ├── Share Domain
   ├── Loan Domain
   ├── Payment Service
   ├── Bank Service
   ├── Ledger
   ├── Reconciliation
   └── Audit
        │
        ▼
    PostgreSQL

We are not currently building:

- Microservices
- Kafka-based architecture
- gRPC services
- Kubernetes
- Service mesh
- Distributed event-driven infrastructure

These may be considered later if real requirements justify them.

---

Rule 5 — Respect Module Boundaries

A module should not directly manipulate another module's internal implementation.

Prefer:

API
 ↓
Service
 ↓
Domain
 ↓
Repository
 ↓
Database

Avoid:

Module A
   ↓
directly modifies
   ↓
Module B's database tables

Use clearly defined service/domain interfaces instead.

---

4. Financial Rules

Rule 6 — Financial Data Is Special

Financial records must be treated differently from ordinary CRUD data.

Never casually:

DELETE payment
DELETE contribution
DELETE ledger entry

If a financial transaction is wrong, use the appropriate mechanism:

Reversal
Refund
Adjustment
Correction

The original transaction should remain traceable.

---

Rule 7 — Never Trust a Client-Supplied Balance

Do not accept:

{
  "balance": 50000
}

from a client and simply store it as the source of truth.

Balances should be derived from authoritative financial records or maintained through controlled accounting logic.

---

Rule 8 — Financial Operations Must Be Atomic

Where multiple database changes represent one financial operation, they must happen inside an appropriate database transaction.

For example:

Payment confirmed
      │
      ├── Payment status updated
      ├── Provider transaction recorded
      └── Ledger entry created

These operations must not leave the database in an inconsistent partial state.

---

Rule 9 — Idempotency Is Mandatory for External Financial Events

External providers may send the same callback more than once.

The system must safely handle duplicate events.

For example:

Provider callback
      ↓
Check provider transaction ID
      ↓
Already processed?
   ├── YES → return safely
   └── NO  → process

Provider transaction identifiers must be uniquely constrained where appropriate.

Example:

UNIQUE(provider, provider_transaction_id)

---

Rule 10 — Never Assume Payment Success

A request being accepted by a provider does not necessarily mean money was successfully received.

Distinguish states such as:

INITIATED
PENDING
SUCCESS
FAILED
CANCELLED
REVERSED

The exact state machine must be defined before implementation.

---

5. Payment Provider Rules

Rule 11 — Never Couple Core Business Logic to a Provider

The Chama domain must not contain code such as:

if provider == "jenga":
    ...

throughout the business logic.

Instead:

Payment Service
      ↓
Provider Resolver
      ↓
PaymentProvider
      ├── Jenga
      ├── KCB BUNI
      ├── NCBA
      └── Daraja

The core system should depend on the abstraction.

---

Rule 12 — Provider-Specific Code Stays in Provider Modules

Provider-specific:

- Authentication
- Request formats
- Response formats
- Callback formats
- Error codes
- Mapping logic

belongs inside the provider adapter.

Do not spread provider-specific code throughout the application.

---

6. Database Rules

Rule 13 — PostgreSQL Is the Source of Truth

Application state must be persisted in PostgreSQL.

Do not use:

Python dictionaries
global variables
temporary files
in-memory state

as authoritative application state.

---

Rule 14 — Every Schema Change Requires a Migration

Never manually modify the production database schema.

Schema changes must go through:

Alembic migration

Example:

alembic revision --autogenerate -m "add memberships"
alembic upgrade head

Migrations must be reviewed before merging.

---

Rule 15 — Do Not Modify Existing Migrations Carelessly

Once a migration has been applied to shared/staging/production environments, do not rewrite its history to fix a new problem.

Create a new migration.

---

Rule 16 — Use Appropriate Constraints

Important business rules should be enforced at the database level where appropriate.

Examples:

NOT NULL
UNIQUE
FOREIGN KEY
CHECK
INDEX

Do not rely exclusively on frontend validation.

---

7. API Rules

Rule 17 — API Contracts Must Be Explicit

Every endpoint should clearly define:

- HTTP method
- URL
- Authentication requirements
- Authorization requirements
- Request schema
- Response schema
- Error responses
- Status codes

Use Pydantic schemas.

---

Rule 18 — Never Return Database Models Directly

Do not expose SQLAlchemy models directly as API responses.

Use dedicated response schemas.

SQLAlchemy Model
       ↓
Service
       ↓
Pydantic Response Schema
       ↓
API

This prevents accidental exposure of internal fields.

---

Rule 19 — Validate Input at the Boundary

Validate incoming data before it reaches business logic.

Examples:

- UUID format
- Amount
- Currency
- Phone number
- Dates
- Enum values
- Required fields

But remember:

«Validation is not the same thing as authorization.»

---

8. Authentication & Authorization

Rule 20 — Authentication ≠ Authorization

Authentication answers:

«Who are you?»

Authorization answers:

«Are you allowed to perform this action?»

Both must be implemented.

---

Rule 21 — Never Trust Role Information From the Client

Never allow the client to decide:

{
  "role": "CHAIRPERSON"
}

and blindly trust it.

Roles and permissions must be determined from server-side state.

---

Rule 22 — Chama-Level Authorization Matters

A user may belong to one Chama but not another.

Every protected Chama operation must verify membership and permissions.

Example:

User
 ↓
Membership
 ↓
Chama
 ↓
Role / Permission
 ↓
Action

---

9. Security Rules

Rule 23 — Never Commit Secrets

Never commit:

API keys
passwords
JWT secrets
database credentials
provider credentials
private keys

to Git.

Use environment variables or approved secret management.

---

Rule 24 — ".env" Files Must Not Be Committed

Use:

.env

locally and maintain:

.env.example

for required configuration names.

Example:

DATABASE_URL=
JENGA_CLIENT_ID=
JENGA_SECRET=

Never put real credentials in ".env.example".

---

Rule 25 — Logs Must Not Leak Sensitive Data

Do not log:

- Passwords
- Access tokens
- API secrets
- Full payment credentials
- Sensitive personal information

Be especially careful with payment provider requests and responses.

---

10. Git Rules

Rule 26 — Never Work Directly on "main"

Developers should work on feature/fix branches.

Example:

git checkout -b feature/member-registration

or:

git checkout -b fix/payment-idempotency

---

Rule 27 — Branch Naming

Use predictable names:

feature/<name>
fix/<name>
refactor/<name>
test/<name>
docs/<name>
chore/<name>

Examples:

feature/contribution-api
feature/loan-application
fix/payment-callback
refactor/payment-provider
test/loan-service
docs/api-authentication

---

Rule 28 — Keep Commits Small and Meaningful

Avoid:

update
changes
final
stuff
working

Prefer:

feat: add contribution creation endpoint
fix: prevent duplicate payment callbacks
test: add loan repayment tests
refactor: isolate provider transaction mapper
docs: document payment lifecycle

---

Rule 29 — One Logical Change Per Commit

Do not combine:

payment feature
UI redesign
database migration
unrelated bug fix

into one giant commit.

Keep changes reviewable.

---

11. Pull Request Rules

Rule 30 — Every PR Must Explain the Change

A PR should contain:

What changed?
Why was it needed?
How was it implemented?
How was it tested?
Are there database changes?
Are there API changes?
Are there security implications?

---

Rule 31 — PRs Must Be Reviewable

Avoid giant PRs where possible.

Prefer:

PR 1 → Database/domain model
PR 2 → Service logic
PR 3 → API
PR 4 → Tests

when splitting provides meaningful review boundaries.

---

Rule 32 — Do Not Merge Your Own PR Without Review

At least one other developer should review changes before merging, unless the team explicitly establishes an emergency procedure.

Financial, authentication, authorization, and payment-provider changes deserve extra scrutiny.

---

12. Code Quality Rules

Rule 33 — Follow Existing Project Conventions

Before creating a new pattern, inspect the existing codebase.

Do not create:

service/
services/
business/
handlers/
managers/

for the same conceptual purpose simply because different developers prefer different names.

Consistency matters.

---

Rule 34 — Avoid Giant Functions

If a function is doing:

validation
authorization
database queries
payment processing
ledger posting
notification

it probably needs to be separated.

---

Rule 35 — Avoid Giant Files

Do not create a 2,000-line:

payment.py

containing every payment-related operation.

Keep responsibilities clear.

---

Rule 36 — Comments Explain Why

Avoid comments that simply repeat the code.

Bad:

# Add one to balance
balance += 1

Better:

# Contribution shares are calculated only after the contribution
# reaches the confirmed state.

---

13. Testing Rules

Rule 37 — New Behavior Requires Tests

If you add business logic, add tests.

Tests should cover:

Expected behavior
Invalid input
Authorization failures
Edge cases
Failure cases
Duplicate requests

---

Rule 38 — Financial Logic Requires Stronger Testing

For financial functionality, test:

- Exact amounts
- Decimal precision
- Duplicate transactions
- Failed transactions
- Reversals
- Partial payments
- Concurrent operations
- Provider callbacks
- Reconciliation
- Ledger consistency

Never use floating-point arithmetic for monetary values.

Use appropriate decimal/numeric handling such as PostgreSQL "NUMERIC" and Python "Decimal".

---

14. Payment Callback Testing

Every provider integration must test at least:

SUCCESS
FAILED
CANCELLED
TIMEOUT
DUPLICATE CALLBACK
UNKNOWN TRANSACTION
INVALID CALLBACK
MALFORMED CALLBACK
REVERSED TRANSACTION

A callback must never blindly change financial records.

---

15. Code Review Checklist

Before approving a PR, reviewers should ask:

Requirements

- [ ] Does this solve the stated problem?
- [ ] Are the business rules correct?

Architecture

- [ ] Does the change respect module boundaries?
- [ ] Is the implementation unnecessarily complex?
- [ ] Is provider-specific code isolated?

Database

- [ ] Are migrations included?
- [ ] Are constraints correct?
- [ ] Are indexes required?

API

- [ ] Is the request validated?
- [ ] Is the response schema explicit?
- [ ] Are errors handled correctly?

Security

- [ ] Is authorization enforced?
- [ ] Are secrets protected?
- [ ] Could sensitive information leak?

Financial correctness

- [ ] Can this create duplicate financial records?
- [ ] Is the operation atomic?
- [ ] Is idempotency handled?
- [ ] Can the transaction be audited?

Testing

- [ ] Are tests included?
- [ ] Are failure cases tested?

---

16. Handling Disagreements

Developers will disagree.

Do not resolve architectural disagreements through:

"I prefer this."

Instead evaluate:

1. Requirements
2. Correctness
3. Security
4. Maintainability
5. Performance
6. Complexity
7. Operational cost
8. Future impact

For significant decisions, document the decision and reasoning.

---

17. Architecture Decision Records

Major architectural decisions should be documented.

Examples:

ADR-001 — Why FastAPI?
ADR-002 — Why PostgreSQL?
ADR-003 — Why Modular Monolith?
ADR-004 — Payment Provider Abstraction
ADR-005 — Financial Ledger Design
ADR-006 — Payment Idempotency Strategy

An ADR should explain:

Context
Decision
Alternatives considered
Reason
Consequences

---

18. No Premature Complexity

Do not introduce technology simply because it is popular.

Before adding a technology, ask:

«What concrete problem does this solve?»

For example, do not add:

Kafka
Redis
RabbitMQ
gRPC
Kubernetes
Microservices
Elasticsearch

unless there is a demonstrated requirement.

A simpler system that is correct is preferable to a complicated system that is difficult to operate.

---

19. Dependencies

Before adding a new dependency, check:

- Is it actually necessary?
- Is there already a dependency that solves the problem?
- Is it maintained?
- Is the license acceptable?
- Does it introduce security risks?
- Does it significantly increase complexity?

Do not add libraries for trivial functionality.

---

20. Documentation Rules

When changing behavior, update relevant documentation.

Documentation may include:

README.md
SDLC.md
API documentation
Architecture documentation
ADR
Database documentation
Provider documentation

Code and documentation should not contradict each other.

---

21. Version Discipline

The roadmap is defined in "SDLC.md".

Developers must not independently invent new version numbers.

The authoritative progression is:

V1  → Chama Foundation
V2  → Financial Management
V3  → Payment Architecture
V4  → Jenga + M-Pesa
V5  → Payment Reliability
V6  → KCB BUNI
V7  → NCBA
V8  → Daraja
V9  → Bank Reconciliation
V10 → Reporting & Audit
V11 → Notifications
V12 → Web
V13 → Mobile
V14 → USSD
V15 → Production Hardening
V16+ → User-driven evolution

Changes to the roadmap must be agreed upon by the project maintainers.

---

22. Do Not Build Future Features Early

If the current version is V1, do not start implementing V8 because the developer is excited about Daraja.

Example:

Current:
V1 → Chama Foundation

Do:
Members
Memberships
Roles
Contributions
Shares

Do not prematurely build:
Daraja
Jenga
KCB BUNI
NCBA
USSD
React Native

Design clean boundaries for future functionality without implementing it prematurely.

---

23. Environment Rules

Maintain separate environments where appropriate:

Development
     ↓
Testing
     ↓
Staging
     ↓
Production

Never use production credentials during local development.

Never test destructive operations against production data.

---

24. Database Backup Rules

Because ChamaCore handles financial records:

- Database backups must exist.
- Backups must be tested.
- Restoration procedures must be documented.
- Production backups must not be treated as optional.

A backup that has never been restored successfully is not considered fully verified.

---

25. Incident Rule

If a serious production financial problem occurs:

Do not silently patch the database.

First:

1. Identify the incident.
2. Preserve relevant logs/audit information.
3. Stop further damage if necessary.
4. Determine affected records.
5. Identify the root cause.
6. Correct the system.
7. Apply controlled financial corrections.
8. Document the incident.
9. Add regression tests.

---

26. Communication Rules

When working on a shared feature:

- State what you are working on.
- State which files/modules you expect to change.
- Communicate database/API changes early.
- Communicate breaking changes before merging.
- Do not silently rewrite another developer's work.
- Ask before changing shared architectural decisions.

---

27. Definition of Done

A feature is not done because:

"It works on my machine."

A feature is done when:

- [ ] Requirements are understood.
- [ ] Business rules are implemented correctly.
- [ ] Database changes are migrated.
- [ ] API contracts are defined.
- [ ] Authorization is implemented.
- [ ] Tests pass.
- [ ] Financial invariants are tested where applicable.
- [ ] Security requirements are satisfied.
- [ ] Documentation is updated.
- [ ] Code has been reviewed.
- [ ] CI passes.
- [ ] The feature is deployable.
- [ ] Known critical defects are resolved.

---

28. Golden Rules

If you remember nothing else, remember these:

1. Understand before coding.

2. Do not invent business rules.

3. Keep modules separated.

4. Financial records must be traceable.

5. Never trust client-side financial state.

6. External payment events must be idempotent.

7. Never commit secrets.

8. Every database change requires a migration.

9. New behavior requires tests.

10. Never introduce complexity without a real reason.

11. Do not merge blindly.

12. "SDLC.md" defines the development process; this "RULES.md" defines the engineering rules.

---

29. Final Team Principle

«We are not just trying to make ChamaCore work. We are trying to build a system that other developers can understand, trust, test, maintain, and safely extend.»

When choosing between:

Fast but fragile

and:

Correct, understandable, and maintainable

we choose the second.

When choosing between:

Complex because it looks impressive

and:

Simple because it solves the actual problem

we choose the second.

Correctness first.
Security second.
Maintainability always.
Complexity only when justified.
