# ChamaCore Backend Completion Specification

**Document:** `CHAMACORE_BACKEND_COMPLETION_SPEC.md`
**Project:** ChamaCore
**Repository:** `Thorium234/Chamacore`
**Purpose:** Force the implementation of the remaining backend financial capabilities without scope creep.

---

# 1. Purpose

This document is the controlling implementation specification for the next stage of ChamaCore.

The objective is **not** to create more infrastructure, redesign the entire application, build a frontend, introduce USSD, or split the system into microservices.

The objective is to finish the backend financial system properly.

The implementation must extend the existing ChamaCore architecture rather than replacing it.

The existing financial foundation must remain intact:

* Chama management
* Users and authentication
* Memberships
* Roles and permissions
* Contributions
* Shares
* Immutable double-entry ledger
* Financial transaction history
* Ledger reversals
* Idempotency
* Chama ownership enforcement
* PostgreSQL constraints
* Payment connections
* Daraja C2B
* STK settlement
* Webhook deduplication
* Authentication hardening
* Structured logging
* Request correlation
* Rate limiting
* Production configuration
* Alembic migrations

The current repository identifies the following unfinished areas:

| Capability                         | Current Status  | Required                                                               |
| ---------------------------------- | --------------- | ---------------------------------------------------------------------- |
| Loans                              | Not implemented | **IMPLEMENT**                                                          |
| Loan repayments                    | Not implemented | **IMPLEMENT**                                                          |
| Payouts                            | Not implemented | **IMPLEMENT**                                                          |
| Aggregated financial reports       | Not implemented | **IMPLEMENT**                                                          |
| Audit event system                 | Not implemented | **IMPLEMENT**                                                          |
| Bank reconciliation                | Not implemented | **IMPLEMENT**                                                          |
| Notifications                      | Not implemented | **IMPLEMENT**                                                          |
| Registration-fee ledger settlement | Blocked         | **RESOLVE AND IMPLEMENT**                                              |
| Frontend                           | Not implemented | **DO NOT IMPLEMENT**                                                   |
| React Native                       | Not implemented | **DO NOT IMPLEMENT**                                                   |
| USSD                               | Not implemented | **DO NOT IMPLEMENT**                                                   |
| Background workers                 | Not implemented | **DO NOT IMPLEMENT UNLESS REQUIRED BY A SPECIFIC BACKEND REQUIREMENT** |
| Microservices                      | Not implemented | **DO NOT IMPLEMENT**                                                   |

---

# 2. Absolute Scope Rule

The system is currently a **backend-first financial platform**.

This specification does not authorize implementation of:

* React
* Next.js
* React Native
* Mobile applications
* USSD
* SMS user interfaces
* Web frontend
* Mobile frontend
* UI component libraries
* Frontend authentication flows
* API gateway services
* Microservices
* Service-to-service architecture
* Kubernetes
* unnecessary message brokers
* unnecessary Redis infrastructure
* unrelated third-party integrations
* speculative AI features
* cryptocurrency features
* blockchain
* unnecessary event-driven architecture

If a task does not directly contribute to the backend capabilities defined in this document, **do not implement it**.

If an agent believes an excluded technology is required, it must first document the exact technical requirement and why the existing architecture cannot satisfy it.

Do not introduce infrastructure merely because it is popular.

---

# 3. Primary Engineering Principle

ChamaCore handles financial information.

Therefore:

> **Correctness takes priority over feature count.**

The implementation must prefer:

1. Financial correctness
2. Database integrity
3. Transaction atomicity
4. Authorization
5. Idempotency
6. Auditability
7. Recoverability
8. Testability
9. Maintainability
10. Performance

Do not sacrifice financial correctness for implementation speed.

---

# 4. Existing Architecture Must Be Preserved

Do not rewrite the existing financial architecture unless a demonstrated defect requires it.

The following principles are mandatory:

### 4.1 Ledger remains authoritative

Balances must not become independently maintained mutable values if they can be derived from posted ledger entries.

Do not introduce:

```text
balance = balance + amount
```

as an alternative source of truth for financial balances.

Financial state must remain connected to the ledger.

### 4.2 Financial transactions remain immutable

Do not edit posted financial transactions.

Corrections must use the existing reversal/compensating-entry model.

### 4.3 Idempotency remains mandatory

Every operation capable of creating a financial transaction must have deterministic duplicate protection.

Retries must not create duplicate financial effects.

### 4.4 Chama isolation remains mandatory

A user operating inside Chama A must never be able to access or mutate financial records belonging to Chama B.

Authorization must be enforced server-side.

Never trust a Chama ID supplied by the client.

---

# 5. Required Implementation Order

The work must proceed in this order.

```text
PHASE 1
Financial-domain clarification

PHASE 2
Loans and repayments

PHASE 3
Payouts

PHASE 4
Registration-fee ledger settlement

PHASE 5
Aggregated financial reporting

PHASE 6
Audit event system

PHASE 7
Bank reconciliation

PHASE 8
Notifications

PHASE 9
Failure/recovery testing

PHASE 10
Production-readiness verification
```

Do not implement these phases simultaneously.

A phase is not complete until its tests and database invariants are complete.

---

# 6. Phase 1: Financial Domain Clarification

Before implementing loans or payouts, inspect:

```text
docs/02_DOMAIN_MODEL.md
docs/03_BUSINESS_RULES.md
docs/04_DATABASE.md
docs/05_ARCHITECTURE.md
docs/06_API_CONTRACT.md
docs/10_V2_FINANCIAL_CORE.md
docs/11_V3_PAYMENT_ARCHITECTURE.md
docs/decisions/
docs/decisions/OPEN_QUESTIONS.md
```

Do not invent missing financial rules.

The existing repository explicitly requires unresolved business rules to be recorded instead of guessed.

Follow that rule.

If a required rule is missing:

1. Record it in `OPEN_QUESTIONS.md`.
2. Create an ADR if the decision affects architecture.
3. Do not implement speculative behavior.
4. Continue only with requirements that are sufficiently defined.

---

# 7. Loans

## 7.1 Objective

Implement a complete backend loan lifecycle.

Minimum lifecycle:

```text
DRAFT
    ↓
SUBMITTED
    ↓
APPROVED
    ↓
DISBURSED
    ↓
PARTIALLY_REPAID
    ↓
REPAID
```

Failure/rejection paths must be explicitly modelled.

At minimum:

```text
SUBMITTED → REJECTED
APPROVED → CANCELLED
```

Do not allow arbitrary state transitions.

---

## 7.2 Loan data

A loan must have an explicit financial identity.

At minimum evaluate and implement:

* loan ID
* Chama ID
* member ID
* principal amount
* interest configuration
* total expected repayment
* outstanding principal
* outstanding interest
* application date
* approval date
* disbursement date
* maturity date
* status
* approved by
* disbursed by
* timestamps

Do not duplicate derived financial values unless there is a documented reason.

---

# 8. Loan Approval

Approval must be authorized.

The applicant must not automatically approve their own loan.

Authorization must verify:

* authenticated user
* active membership
* correct Chama
* required role
* loan status
* approval permissions

Every approval must produce an audit event.

---

# 9. Loan Disbursement

Disbursement is a financial event.

It must be atomic.

The system must not reach this state:

```text
Loan marked DISBURSED
+
No ledger transaction
```

or:

```text
Ledger disbursement posted
+
Loan remains APPROVED
```

The state transition and financial posting must be coordinated inside an appropriate database transaction.

Disbursement must be idempotent.

A retry must not produce a second disbursement.

---

# 10. Loan Ledger Integration

Loans must integrate with the existing double-entry ledger.

Do not create a second accounting system.

The exact accounts must be documented through an ADR before implementation.

The implementation must establish the correct accounting treatment for:

* loan principal
* loan disbursement
* loan repayment
* interest
* outstanding loan balances
* reversals

Example conceptual flow:

```text
Loan disbursement

Debit:
    Loans Receivable

Credit:
    Cash
```

Example conceptual repayment:

```text
Loan repayment

Debit:
    Cash

Credit:
    Loans Receivable
    Interest Income
```

The exact account structure must follow the approved ChamaCore accounting rules.

---

# 11. Loan Repayments

Repayments must support:

* full repayment
* partial repayment
* repeated repayments
* idempotent repayment requests
* repayment reversal
* outstanding balance calculation
* repayment history

The system must prevent:

```text
repayment > outstanding amount
```

unless overpayments are explicitly defined by an approved business rule.

Do not silently invent overpayment behavior.

---

# 12. Loan Repayment Allocation

If repayment contains both principal and interest, the allocation order must be explicit.

For example:

```text
Interest
    ↓
Principal
```

or another formally approved rule.

Do not hard-code an arbitrary allocation order without documenting the business rule.

---

# 13. Payouts

Payouts represent money leaving the Chama.

They therefore require stronger controls than ordinary CRUD operations.

Minimum lifecycle:

```text
REQUESTED
    ↓
APPROVED
    ↓
PROCESSING
    ↓
COMPLETED
```

Failure paths:

```text
REQUESTED → REJECTED
PROCESSING → FAILED
```

Do not allow direct:

```text
REQUESTED → COMPLETED
```

without appropriate authorization and financial recording.

---

# 14. Payout Authorization

Payouts must have authorization rules.

At minimum:

* requester cannot approve their own payout
* payout must belong to the correct Chama
* amount must be valid
* Chama must be active
* user must have appropriate permission
* payout must not already be completed
* duplicate approval must not create another payout

Large payouts may require multiple approvals if the business rules define thresholds.

Do not invent multi-signature behavior unless requirements explicitly require it.

---

# 15. Payout Ledger Integration

A completed payout must produce the appropriate ledger transaction.

The system must never mark a payout as completed without its corresponding financial record.

The system must also never create the financial record while leaving the payout state inconsistent.

Use database transactions.

Payouts must support compensating reversals where appropriate.

Do not delete completed payouts.

---

# 16. Registration Fee Ledger Settlement

The repository currently identifies registration-fee ledger settlement as blocked.

Resolve the underlying open question.

Determine:

* whether registration fees belong to income
* whether they belong to a specific account
* whether waived fees create financial entries
* whether historical fees need migration
* how payment and ledger posting interact
* whether cash and electronic payment use the same accounting flow

After resolution:

1. Create or update the relevant ADR.
2. Implement the ledger posting.
3. Add migration if required.
4. Add unit tests.
5. Add integration tests.
6. Add reversal tests.
7. Add idempotency tests.

---

# 17. Aggregated Financial Reporting

Implement backend reporting APIs only.

No frontend reporting screens.

Required reporting capabilities should include:

### Chama summary

* total contributions
* total shares
* total loans
* outstanding loans
* total interest
* total repayments
* total payouts
* available cash based on ledger
* financial period

### Member financial summary

* contributions
* shares
* loans
* repayments
* outstanding loan balance
* payouts where applicable

### Loan reports

* total disbursed
* total repaid
* outstanding principal
* outstanding interest
* overdue loans
* repayment history

### Ledger reports

* account balances
* transaction totals
* debits
* credits
* financial period filtering

Reports must be generated from authoritative financial data.

Do not maintain separate fake reporting balances.

---

# 18. Reporting Performance

Reporting queries must not destroy database performance.

Use:

* appropriate indexes
* aggregation queries
* pagination
* date filtering
* Chama-scoped queries

Do not load an entire Chama's financial history into Python just to calculate totals.

Prefer database aggregation.

If a report becomes expensive, measure it before introducing caching.

Do not introduce Redis simply to make an unoptimized query appear faster.

---

# 19. Audit Event System

Implement a dedicated audit event system.

This is separate from the financial ledger.

The ledger answers:

> What happened financially?

The audit system answers:

> Who performed the action, when, against what resource, and from which request?

Minimum fields should include:

```text
id
chama_id
actor_user_id
action
resource_type
resource_id
request_id
timestamp
success
metadata
```

Where appropriate also capture:

```text
IP address
user agent
```

Do not store secrets, passwords, access tokens, refresh tokens, or payment credentials.

---

# 20. Audit Events

Audit important actions including:

### Authentication

* login
* failed login where appropriate
* logout
* refresh
* identity claim

### Membership

* member creation
* member status change
* role assignment
* role removal

### Contributions

* creation
* confirmation
* reversal

### Loans

* application
* approval
* rejection
* disbursement
* repayment
* repayment reversal

### Payouts

* request
* approval
* rejection
* processing
* completion
* failure

### Payment configuration

* payment connection creation
* activation
* suspension
* credential changes
* C2B registration

### Administrative actions

* Chama status changes
* permission changes
* sensitive configuration changes

Audit events must be append-only.

---

# 21. Audit Event Security

Audit records must not be editable through ordinary application APIs.

Do not implement:

```text
PUT /audit-events/{id}
DELETE /audit-events/{id}
```

Audit history must be treated as immutable evidence.

Database-level protection should be considered where appropriate.

---

# 22. Bank Reconciliation

Implement reconciliation as a backend financial control.

The objective is to compare external financial records with ChamaCore's internal records.

Minimum conceptual flow:

```text
External statement
        ↓
Import
        ↓
Normalize
        ↓
Match
        ↓
Matched
        ↓
Exception
        ↓
Resolution
```

The system must support:

* statement import
* transaction identity
* transaction date
* amount
* reference
* external identifier
* matching status
* internal transaction reference
* reconciliation status

---

# 23. Reconciliation Rules

Matching must not rely solely on amount.

Where available, use:

* external transaction ID
* reference
* account
* amount
* date
* transaction type

Potential states:

```text
UNMATCHED
MATCHED
DISPUTED
RESOLVED
IGNORED
```

Do not silently force unmatched transactions into the ledger.

---

# 24. Reconciliation Safety

Reconciliation must never directly rewrite historical ledger entries.

If a discrepancy represents a real financial correction:

```text
identify discrepancy
        ↓
determine cause
        ↓
authorized correction
        ↓
compensating ledger transaction
        ↓
audit event
```

Never mutate historical financial records to make reconciliation appear successful.

---

# 25. Notifications

Implement notifications as a backend capability only.

No frontend notification UI.

Notifications should initially cover important financial events.

Examples:

```text
Loan approved
Loan rejected
Loan disbursed
Loan repayment received
Loan nearing due date
Loan overdue
Contribution confirmed
Contribution reversed
Payout requested
Payout approved
Payout completed
Payout failed
Payment received
Reconciliation exception
```

---

# 26. Notification Architecture

Do not immediately introduce a complex distributed messaging system.

Start with a provider-neutral notification domain.

Conceptually:

```text
Domain Event
     ↓
Notification Record
     ↓
Delivery Attempt
     ↓
Provider
```

The notification record should track:

```text
id
recipient
event type
channel
payload
status
attempt count
created_at
sent_at
failure reason
```

Channels can initially be limited to what is actually required.

Do not implement USSD.

Do not implement a mobile notification interface.

Do not implement unnecessary providers.

---

# 27. Notification Idempotency

The same domain event must not create unlimited duplicate notifications.

A deterministic notification key should be used where appropriate.

Example:

```text
loan-approved:{loan_id}:{recipient_id}
```

Retrying notification delivery must not create duplicate logical notifications.

---

# 28. Background Processing

Do not introduce background workers merely because notifications exist.

First implement the notification domain and delivery abstraction.

If asynchronous delivery becomes necessary, document the exact requirement.

Only then evaluate a worker architecture.

Do not introduce Celery, Redis, Kafka, RabbitMQ, or another queue simply because they are common technologies.

---

# 29. API Requirements

Every new API must have:

* authentication
* authorization
* request validation
* response schema
* Chama isolation
* transaction handling
* idempotency where financial effects occur
* appropriate HTTP status codes
* tests
* documentation

Do not create unprotected administrative endpoints.

Do not trust client-supplied authorization information.

---

# 30. Database Requirements

Every database change must use Alembic.

Never manually modify production schema.

Financial tables must receive appropriate:

* foreign keys
* composite Chama ownership constraints
* CHECK constraints
* unique constraints
* indexes
* append-only protection where required

Database integrity must not depend entirely on Python validation.

---

# 31. Testing Requirements

Every implemented feature requires tests.

Minimum categories:

```text
Unit tests
Integration tests
Authorization tests
Database constraint tests
Idempotency tests
Transaction rollback tests
Concurrency tests where applicable
Financial invariant tests
API contract tests
```

Financial features require negative tests.

Do not only test successful operations.

---

# 32. Mandatory Failure Tests

For loans:

```text
duplicate approval
duplicate disbursement
unauthorized approval
cross-Chama access
repayment exceeding balance
duplicate repayment
failed ledger posting
rollback during disbursement
```

For payouts:

```text
duplicate approval
duplicate completion
unauthorized payout
cross-Chama access
failed payout
ledger failure
retry after failure
```

For payments:

```text
duplicate callback
conflicting callback
callback replay
unknown member
inactive member
wrong connection
concurrent callbacks
```

For reconciliation:

```text
duplicate external transaction
unmatched transaction
incorrect amount
duplicate matching
cross-Chama transaction
```

For audit:

```text
missing actor
cross-Chama audit access
audit modification attempt
audit deletion attempt
```

---

# 33. Financial Invariants

The implementation must continuously enforce financial invariants.

At minimum:

```text
Total debits = Total credits
```

for every balanced financial transaction.

Additional invariants must include:

```text
Completed financial operation → corresponding ledger transaction

Reversed transaction → valid compensating transaction

One logical operation → one financial effect

Unauthorized user → zero financial mutation

Cross-Chama request → rejected

Duplicate financial request → no duplicate financial effect
```

Loan-specific:

```text
Outstanding principal >= 0
Outstanding interest >= 0
Repaid amount <= applicable repayment obligation
```

Payout-specific:

```text
Completed payout has financial record
Completed payout cannot be completed again
```

---

# 34. No Silent Data Mutation

Never silently repair inconsistent financial data.

Bad:

```text
if balance_is_wrong:
    balance = calculated_balance
```

Correct approach:

```text
detect inconsistency
record exception
identify cause
authorize correction
create compensating financial transaction
audit correction
```

---

# 35. No Destructive Migrations

Never destroy existing financial records to accommodate new features.

Migrations must preserve:

* contributions
* ledger transactions
* ledger entries
* payment records
* memberships
* users
* Chamas
* historical financial information

If restructuring is unavoidable:

1. backup
2. migration
3. validation
4. reconciliation
5. rollback plan

---

# 36. No Fake Completion

An agent must never mark a capability as implemented merely because:

* models exist
* endpoints exist
* migrations exist
* tests are superficial
* happy-path tests pass

A feature is complete only when:

```text
Domain rules implemented
+
Database integrity implemented
+
Authorization implemented
+
Financial integration implemented
+
Failure handling implemented
+
Idempotency implemented where required
+
Tests implemented
+
Documentation updated
```

---

# 37. Definition of Done

A feature is considered DONE only when all of the following are true:

* [ ] Domain model exists
* [ ] Business rules documented
* [ ] ADR created when architecture changes
* [ ] Database migration created
* [ ] Database constraints implemented
* [ ] API schemas implemented
* [ ] Authorization implemented
* [ ] Chama isolation verified
* [ ] Financial ledger integration completed where applicable
* [ ] Idempotency implemented where applicable
* [ ] Reversal behavior implemented where applicable
* [ ] Audit events implemented
* [ ] Unit tests written
* [ ] Integration tests written
* [ ] Negative tests written
* [ ] Concurrency tests written where applicable
* [ ] Documentation updated
* [ ] Existing tests still pass
* [ ] No unrelated feature introduced

---

# 38. Forbidden Scope Expansion

The following must NOT appear in implementation pull requests for this specification:

```text
React
React Native
Next.js
USSD
Frontend components
Mobile screens
UI redesign
CSS
Tailwind
Frontend state management
Microservices
Kubernetes
Kafka
RabbitMQ
Redis
GraphQL
AI features
Blockchain
Cryptocurrency
Unrequested payment providers
Unrequested notification providers
```

An infrastructure component may only be introduced if a documented backend requirement proves that the existing architecture cannot satisfy the requirement.

---

# 39. Existing Architecture Rule

Do not replace working infrastructure merely for preference.

If an existing implementation works:

```text
keep it
```

If it is incorrect:

```text
prove the defect
document the defect
write a regression test
fix the defect
```

Do not perform speculative rewrites.

---

# 40. Performance Rule

Do not optimize based on assumptions.

Measure first.

Required tools include:

* database query plans
* indexes
* query timing
* API latency
* test timing
* transaction contention

Do not add caching before identifying the actual bottleneck.

Do not add Redis simply because a query is slow.

Fix the query first.

---

# 41. Security Rule

All new financial endpoints must be evaluated against:

```text
Authentication
Authorization
Object-level authorization
Chama isolation
Input validation
Replay attacks
Duplicate requests
Concurrent requests
Privilege escalation
Information leakage
Sensitive data exposure
```

Payment credentials and secrets must never appear in:

* logs
* audit metadata
* API responses
* exception messages
* test fixtures committed to Git

---

# 42. Documentation Rule

When implementing each feature, update:

```text
docs/00_PROJECT_STATUS.md
docs/01_PRODUCT_REQUIREMENTS.md
docs/02_DOMAIN_MODEL.md
docs/03_BUSINESS_RULES.md
docs/04_DATABASE.md
docs/05_ARCHITECTURE.md
docs/06_API_CONTRACT.md
docs/08_ROADMAP.md
```

Only update documents that are actually affected.

Add ADRs for architectural decisions.

Update the test inventory.

Do not claim a feature is complete until its documentation reflects reality.

---

# 43. Required Final Backend Scope

After this specification is completed, ChamaCore should provide a coherent backend for:

```text
                    ChamaCore
                       │
        ┌──────────────┼──────────────┐
        │              │              │
   Identity       Chama Core      Financial Core
        │              │              │
 Authentication    Memberships     Contributions
 Roles             Roles           Shares
 Permissions       Chama           Loans
                                   Repayments
                                   Payouts
                                   Ledger
                                   Reversals
                                   Reconciliation
                                   Reports
        │              │              │
        └──────────────┼──────────────┘
                       │
                  Payment Core
                       │
                  Daraja C2B
                  STK Settlement
                  Webhooks
                       │
                Audit + Operations
                       │
                  Audit Events
                  Notifications
                  Observability
```

This is the target backend.

No frontend is required for completion of this specification.

No USSD is required for completion of this specification.

---

# 44. Final Completion Matrix

The final project status should eventually become:

| Capability                          | Status           |
| ----------------------------------- | ---------------- |
| Authentication                      | Implemented      |
| Users                               | Implemented      |
| Chamas                              | Implemented      |
| Memberships                         | Implemented      |
| Roles and permissions               | Implemented      |
| Contributions                       | Implemented      |
| Shares                              | Implemented      |
| Double-entry ledger                 | Implemented      |
| Ledger reversals                    | Implemented      |
| Payment connections                 | Implemented      |
| Daraja C2B                          | Implemented      |
| STK settlement                      | Implemented      |
| Webhook deduplication               | Implemented      |
| Loan applications                   | **Required**     |
| Loan approval                       | **Required**     |
| Loan disbursement                   | **Required**     |
| Loan repayments                     | **Required**     |
| Loan reversals                      | **Required**     |
| Payout requests                     | **Required**     |
| Payout approvals                    | **Required**     |
| Payout processing                   | **Required**     |
| Payout ledger integration           | **Required**     |
| Registration-fee ledger settlement  | **Required**     |
| Aggregated financial reports        | **Required**     |
| Audit event system                  | **Required**     |
| Bank reconciliation                 | **Required**     |
| Notifications                       | **Required**     |
| Failure/recovery workflows          | **Required**     |
| Financial invariant tests           | **Required**     |
| PostgreSQL concurrency verification | **Required**     |
| Production verification             | **Required**     |
| React frontend                      | **OUT OF SCOPE** |
| React Native                        | **OUT OF SCOPE** |
| USSD                                | **OUT OF SCOPE** |
| Microservices                       | **OUT OF SCOPE** |

---

# 45. Agent Execution Rules

Any coding agent working on ChamaCore must obey these rules.

### Rule 1

Read the repository documentation before changing code.

### Rule 2

Inspect the existing implementation before creating new models.

### Rule 3

Never duplicate an existing financial concept.

### Rule 4

Never bypass the ledger.

### Rule 5

Never bypass authorization.

### Rule 6

Never bypass Chama isolation.

### Rule 7

Never mutate posted financial records.

### Rule 8

Never create financial effects without idempotency where retry is possible.

### Rule 9

Never invent unresolved business rules.

### Rule 10

Never introduce frontend, USSD, or mobile functionality.

### Rule 11

Never introduce infrastructure without a demonstrated requirement.

### Rule 12

Never delete or weaken an existing test merely to make the suite pass.

### Rule 13

Never mark a feature complete without integration tests.

### Rule 14

Never hide failures.

### Rule 15

Never silently change financial data.

### Rule 16

When an implementation requirement conflicts with an existing ADR, stop and resolve the conflict before coding.

### Rule 17

When requirements are ambiguous, record the ambiguity instead of guessing.

### Rule 18

Every financial mutation must have a traceable path:

```text
API request
    ↓
authorization
    ↓
domain validation
    ↓
database transaction
    ↓
financial mutation
    ↓
ledger entry where applicable
    ↓
audit event
    ↓
response
```

---

# 46. Completion Standard

ChamaCore is considered complete for this backend phase only when the system can reliably demonstrate:

```text
A member can contribute.

A contribution can become a ledger transaction.

A contribution can be reversed without mutating history.

A member can apply for a loan.

An authorized person can approve it.

The loan can be disbursed exactly once.

Repayments can be recorded correctly.

Loan balances remain financially consistent.

An authorized user can request a payout.

An authorized user can approve it.

The payout produces the correct financial transaction.

External financial records can be reconciled.

Financial reports can be generated from authoritative records.

Important actions generate immutable audit events.

Important financial events can generate notifications.

Duplicate requests do not create duplicate financial effects.

Unauthorized users cannot cross Chama boundaries.

Database constraints protect the financial model.

Failures roll back safely.

Historical financial records remain immutable.

The entire system remains testable and recoverable.
```

Anything outside this list is secondary.

---

# 47. Final Directive

**Do not add more features until these requirements are satisfied.**

The goal is not to make ChamaCore look bigger.

The goal is to make ChamaCore **financially correct, auditable, secure, recoverable, and operationally trustworthy**.

Finish the backend.

Prove it.

Then stop.

Do not expand the scope.
