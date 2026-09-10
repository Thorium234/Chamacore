ChamaCore Software Development Life Cycle

1. Purpose

ChamaCore follows a practical, iterative Software Development Life Cycle designed around the actual needs of a financial Chama platform.

The development philosophy is:

Understand
    ↓
Specify
    ↓
Analyze
    ↓
Design
    ↓
Implement
    ↓
Test
    ↓
Deploy
    ↓
Observe
    ↓
Improve
    ↺

Every major version of ChamaCore goes through this cycle.

We do not build the entire platform at once.

For example:

V1 → Complete SDLC cycle
V2 → Complete SDLC cycle
V3 → Complete SDLC cycle
...

The objective is to continuously produce a working, tested and deployable system.

---

2. Current Architecture Direction

ChamaCore is currently designed as a:

«Modular monolith with provider-agnostic payment and banking integrations.»

The initial backend is:

FastAPI
   ↓
SQLAlchemy
   ↓
PostgreSQL

External providers are isolated behind interfaces.

                    FastAPI
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
   Chama Domain   Payment Service   Bank Service
                       │
                       ▼
               Provider Resolver
                       │
       ┌───────────────┼───────────────┐
       ▼               ▼               ▼
     Jenga          KCB BUNI          NCBA
       │               │               │
     Equity            KCB            NCBA

                       +
                    Daraja
                       │
                    M-Pesa

We deliberately avoid premature microservices.

The architecture can evolve later if real requirements justify service extraction.

---

3. Core Development Principle

«Never implement a feature before we understand its business requirement, domain model, API contract and test cases.»

For every feature:

Business Requirement
        ↓
Domain Analysis
        ↓
Data Model
        ↓
API Contract
        ↓
Implementation
        ↓
Tests
        ↓
Deployment
        ↓
Feedback

---

PHASE 1 - Problem & Product Definition

Before writing code, establish what problem ChamaCore is solving.

Problem

Traditional Chamas may depend on:

- Exercise books
- Excel
- WhatsApp
- M-Pesa messages
- Manual calculations
- Manual reconciliation

This can create:

- Missing records
- Calculation errors
- Poor contribution visibility
- Difficult loan tracking
- Difficult financial reporting
- Difficult reconciliation
- Lack of accountability

Product Vision

ChamaCore is a digital platform for managing:

- Chamas
- Members
- Contributions
- Shares
- Loans
- Loan repayments
- Payouts
- Financial transactions
- Payments
- Bank accounts
- Reconciliation
- Reports

The long-term platform will support:

- Web
- Mobile
- USSD
- Kenyan payment providers
- Banking integrations

Technology is selected to solve the problem, not the other way around.

---

PHASE 2 - Requirements Engineering

Requirements are divided into:

Functional Requirements
Non-Functional Requirements

Functional Requirements

V1

FR1  Create Chama
FR2  Update Chama
FR3  View Chama
FR4  Manage Chama status
FR5  Add members
FR6  Update members
FR7  Remove/deactivate members
FR8  Assign roles
FR9  Manage registration fees
FR10 Manage contribution rules
FR11 Record contributions
FR12 Track shares

V2

FR13 Create loans
FR14 Approve/reject loans
FR15 Record loan disbursement
FR16 Record loan repayments
FR17 Manage payouts
FR18 Record financial transactions
FR19 Maintain financial ledger
FR20 Generate member statements

Payment Versions

FR21 Create payment
FR22 Initiate payment
FR23 Select payment provider
FR24 Initiate M-Pesa STK
FR25 Receive provider callback
FR26 Verify payment
FR27 Update payment status
FR28 Link payment to contribution
FR29 Prevent duplicate processing
FR30 Reconcile external transactions

Banking

FR31 Register Chama bank account
FR32 Retrieve supported account information
FR33 Retrieve balance where supported
FR34 Retrieve transactions where supported
FR35 Retrieve statements where supported
FR36 Reconcile bank transactions

Future

FR37 Notifications
FR38 Financial reports
FR39 Audit logs
FR40 React web application
FR41 React Native application
FR42 USSD
FR43 Multi-Chama management

---

PHASE 3 - Non-Functional Requirements

ChamaCore must prioritize:

Security

- Authentication
- Authorization
- Password hashing
- Secure secrets
- HTTPS
- Input validation
- Webhook verification

Reliability

Financial transactions must not disappear or be duplicated.

Data Integrity

Financial records must remain consistent.

Maintainability

Provider integrations must remain isolated from business logic.

Observability

The system must provide enough logs and metrics to understand failures.

Performance

Normal API requests should have acceptable response times under expected usage.

Availability

Production services should be monitored and recoverable.

Auditability

Important financial actions must be traceable.

---

PHASE 4 - System Analysis

This phase models how a real Chama works.

Example:

Chama
 │
 ├── Members
 │
 ├── Contributions
 │
 ├── Shares
 │
 ├── Loans
 │
 ├── Loan Repayments
 │
 ├── Payouts
 │
 ├── Payments
 │
 └── Bank Account

We ask business questions before implementation.

Examples:

Can a non-member contribute?

No.

Can a member belong to multiple Chamas?

The data model should support this.

Therefore:

User
  ↓
Membership
  ↓
Chama

rather than putting "chama_id" directly on the user.

Can a successful payment be deleted?

No.

Financial history must be preserved.

Corrections should use:

Reversal
Refund
Adjustment

depending on the situation.

Does a bank account number automatically give ChamaCore access to transactions?

No.

A bank account number is only identifying information.

Actual transaction visibility requires an appropriate bank/provider integration, statement import or another supported reconciliation mechanism.

---

PHASE 5 - Domain & Financial Model Design

This is one of the most important phases.

ChamaCore separates:

Contribution
Payment
Provider Transaction
Bank Transaction
Ledger Entry

These are not the same thing.

The core relationship is:

Member
   ↓
Contribution
   ↓
Payment
   ↓
Provider Transaction
   ↓
Ledger Entry

Bank-side information is separate:

Bank Account
   ↓
Bank Transaction
   ↓
Reconciliation
   ↓
Ledger

---

PHASE 6 - Architecture Design

The initial architecture is a modular monolith.

ChamaCore
│
├── Authentication
├── Chama
├── Members
├── Contributions
├── Shares
├── Loans
├── Payouts
├── Payments
├── Ledger
├── Banking
├── Reconciliation
├── Notifications
├── Reports
└── Audit

All modules initially run inside one FastAPI application.

This avoids premature distributed-system complexity.

---

PHASE 7 - Payment Architecture Design

Payment integration is deliberately separated from Chama business logic.

Payment Provider

PaymentProvider
│
├── initiate_payment()
├── get_payment_status()
├── handle_callback()
├── verify_transaction()
├── refund_payment()
└── reconcile()

Implementations:

JengaPaymentProvider
KCBPaymentProvider
NCBAPaymentProvider
DarajaPaymentProvider

The application communicates with the abstraction rather than a specific provider.

Example:

ContributionService
       ↓
PaymentService
       ↓
ProviderResolver
       ↓
Jenga / KCB / NCBA / Daraja

---

PHASE 8 - Banking Architecture Design

Banking functionality is separated from payment processing.

Bank Provider

BankProvider
│
├── get_balance()
├── get_transactions()
├── get_statement()
├── validate_account()
└── reconcile()

Possible implementations:

JengaBankProvider
KCBBankProvider
NCBABankProvider

The exact capabilities available depend on the provider, bank and approved API products.

ChamaCore must never assume that every bank exposes identical APIs.

---

PHASE 9 - Database Design

PostgreSQL is the primary database.

SQLAlchemy handles application/database mapping.

Alembic manages schema migrations.

Core tables

users
chamas
memberships
roles

contributions
shares

loans
loan_repayments
payouts

payments
payment_attempts
provider_transactions
provider_callbacks

bank_accounts
bank_transactions

ledger_accounts
ledger_entries

reconciliation_records

audit_logs
notifications

Financial data must have appropriate constraints and indexes.

Important uniqueness rules include provider transaction identifiers.

Example:

UNIQUE(provider, provider_transaction_id)

---

PHASE 10 - API Design

All APIs should use versioning.

Example:

/api/v1/chamas
/api/v1/members
/api/v1/contributions
/api/v1/loans
/api/v1/payments
/api/v1/bank-accounts
/api/v1/reconciliation

Webhooks are separated:

/api/v1/webhooks/jenga
/api/v1/webhooks/kcb
/api/v1/webhooks/ncba
/api/v1/webhooks/daraja

API contracts should define:

- Request schema
- Response schema
- HTTP status
- Validation rules
- Error format
- Authentication requirements
- Authorization requirements

OpenAPI documentation should be generated from FastAPI.

---

PHASE 11 - Implementation

Development is incremental.

Sprint 1 - Foundation

FastAPI
PostgreSQL
SQLAlchemy
Alembic
Configuration
Project structure

Sprint 2 - Chama

Chama model
Chama schema
Repository
Service
Router
Tests

Sprint 3 - Members

Membership
Roles
Member service
Member API
Tests

Sprint 4 - Contributions & Shares

Contribution
Share
Contribution rules
Contribution history
Tests

Sprint 5 - Loans & Payouts

Loans
Repayments
Payouts
Ledger
Tests

Sprint 6 - Payment Architecture

Payment model
PaymentAttempt
ProviderTransaction
PaymentProvider interface
Provider resolver

Sprint 7 - Jenga

Jenga authentication
STK Push
Payment status
Callbacks
Transaction mapping

Sprint 8 - Reconciliation

Idempotency
Provider reconciliation
Unknown transactions
Failed transactions
Reversals

Sprint 9 - Additional Providers

KCB BUNI
NCBA
Daraja

Sprint 10 - Banking

BankProvider
Balance
Statements
Transactions
Bank reconciliation

---

PHASE 12 - Testing

Testing happens continuously.

Do not wait until the entire application is finished.

Unit Tests

Test individual business operations.

Example:

calculate_loan_balance()
calculate_contribution_total()
calculate_chama_balance()
validate_contribution()

Integration Tests

Test:

FastAPI
   ↓
Service
   ↓
Repository
   ↓
PostgreSQL

API Tests

Example:

POST /api/v1/chamas

Verify:

HTTP status
Response schema
Database record
Validation
Authorization

Provider Tests

Test provider adapters independently.

Jenga
KCB
NCBA
Daraja

Use sandbox environments where available.

---

PHASE 13 - Financial Testing

Financial operations require additional testing.

Test:

Successful payment
Failed payment
Pending payment
Cancelled payment
Reversed payment
Duplicate callback
Unknown transaction
Partial payment
Multiple contributions
Loan repayment
Payout
Bank reconciliation

Example duplicate callback:

Callback #1
ABC123
   ↓
Process

Callback #2
ABC123
   ↓
Already processed
   ↓
Ignore

The system must never create two financial credits from one external transaction.

---

PHASE 14 - Security

Security is implemented progressively.

Foundation

Environment variables
Password hashing
Input validation
Secure configuration

Authentication

Register
   ↓
Login
   ↓
Authentication
   ↓
Access token
   ↓
Protected API

Authorization

Roles:

MEMBER
SECRETARY
TREASURER
CHAIRPERSON
ADMIN

Permissions must be enforced at the service/API level.

For example:

MEMBER
   → View own contributions

TREASURER
   → Manage financial records

CHAIRPERSON
   → Approve authorized operations

---

PHASE 15 - Audit

Financial and administrative operations must be auditable.

Record events such as:

MEMBER_CREATED
CONTRIBUTION_CREATED
PAYMENT_INITIATED
PAYMENT_COMPLETED
PAYMENT_FAILED
LOAN_APPROVED
LOAN_DISBURSED
LOAN_REPAID
PAYOUT_CREATED
TRANSACTION_REVERSED
BANK_TRANSACTION_RECONCILED

Audit records should contain enough information to establish:

Who
What
When
Which record
Previous state
New state

---

PHASE 16 - Deployment

The first deployment should remain simple.

GitHub
   ↓
CI/CD
   ↓
Production
   │
   ├── FastAPI
   ├── PostgreSQL
   ├── HTTPS
   ├── Environment variables
   ├── Logs
   └── Backups

Do not introduce Kubernetes or a complex cloud architecture without a real requirement.

---

PHASE 17 - Monitoring & Maintenance

After deployment, monitor:

API errors
Request latency
Database performance
Server resources
Failed payments
Payment callbacks
Provider failures
Reconciliation failures

For financial operations, pay particular attention to:

Duplicate payments
Failed payments
Pending payments
Reversals
Unknown transactions
Missing callbacks
Bank mismatches

---

PHASE 18 - User Feedback

Production feedback becomes the next source of requirements.

Example:

Users
  ↓
"We don't want to manually record contributions."
  ↓
Requirement
  ↓
Analysis
  ↓
Payment integration
  ↓
Design
  ↓
Implementation
  ↓
Testing
  ↓
Deployment

The SDLC then loops.

---

19. Version Roadmap

Version| Main Objective
V1| Chama + Members + Roles + Contributions + Shares
V2| Loans + Repayments + Payouts + Ledger
V3| Payment architecture + PaymentProvider
V4| Jenga + M-Pesa STK
V5| Webhooks + Payment reconciliation + Idempotency
V6| KCB BUNI
V7| NCBA
V8| Daraja
V9| Bank reconciliation
V10| Reports + Statements + Audit
V11| Notifications
V12| React Web
V13| React Native
V14| USSD
V15| Production hardening + advanced operations
V16+| New requirements based on real users

---

20. SDLC Applied to Each Version

Every version follows:

                VERSION
                   │
                   ▼
          Problem / Requirement
                   │
                   ▼
              Analysis
                   │
                   ▼
        Domain + Architecture
                   │
                   ▼
          Database + API Design
                   │
                   ▼
             Development
                   │
                   ▼
               Testing
                   │
                   ▼
              Deployment
                   │
                   ▼
         Monitoring / Feedback
                   │
                   ▼
             Next Version
                   │
                   └───────────────↺

We do not move to the next version simply because the code "works on my machine."

A version is complete when its requirements have been implemented, tested and deployed to an appropriate environment.

---

21. Evolution of the Architecture

ChamaCore starts as:

Modular Monolith

The intended evolution is:

Modular Monolith
       ↓
Better domain boundaries
       ↓
Provider abstraction
       ↓
Reliable integrations
       ↓
Production monitoring
       ↓
Identify actual bottlenecks
       ↓
Extract services only where justified

If the platform eventually requires distributed architecture, services can be extracted from already-defined modules.

Possible future services could include:

Identity Service
Chama Service
Member Service
Contribution Service
Payment Service
Ledger Service
Notification Service
Reporting Service

Messaging such as Kafka or internal communication such as gRPC should only be introduced when there is a genuine architectural requirement.

They are not part of V1 merely for the sake of calling the project microservices.

---

22. Definition of Done

A feature is considered complete only when:

Requirement understood
        ↓
Domain rules defined
        ↓
Database model designed
        ↓
API contract defined
        ↓
Implementation completed
        ↓
Unit tests written
        ↓
Integration/API tests written
        ↓
Security checked
        ↓
Documentation updated
        ↓
Deployed
        ↓
Verified

For financial features, additionally:

Idempotency checked
Auditability checked
Reconciliation considered
Failure scenarios tested

---

23. The Most Important Financial Rule

ChamaCore must always be able to answer:

«Who contributed what, when, through which payment mechanism, what external transaction confirmed it, and how was it reflected in the Chama's financial records?»

The transaction chain should be traceable:

Member
  ↓
Contribution
  ↓
Payment
  ↓
Payment Attempt
  ↓
Provider Transaction
  ↓
Reconciliation
  ↓
Ledger Entry
  ↓
Financial Statement

This is the foundation of the system.

---

24. Current Development Target

The immediate target is V1.

V1
│
├── Chama
├── Members
├── Memberships
├── Roles
├── Registration Fees
├── Contributions
└── Shares

Then:

V1
 ↓
V2 Financial Domain
 ↓
V3 Payment Architecture
 ↓
V4 Jenga
 ↓
V5 Reconciliation
 ↓
V6 KCB
 ↓
V7 NCBA
 ↓
V8 Daraja
 ↓
V9 Banking
 ↓
V10 Reports/Audit
 ↓
V11 Notifications
 ↓
V12 Web
 ↓
V13 Mobile
 ↓
V14 USSD

---

25. Project Development Rule

Build the product first. Add complexity when the product requires it.

We will not introduce:

Kafka
gRPC
Microservices
Kubernetes
Service Mesh
Complex Event Sourcing
Multiple Databases

simply because they are technologies we know or want to learn.

The current system should be:

FastAPI
+
PostgreSQL
+
Modular Architecture
+
Clean Domain Boundaries
+
Provider Abstractions
+
Reliable Financial Transactions

If future requirements justify distributed architecture, ChamaCore will evolve into it deliberately.

---

26. Final SDLC

┌───────────────────────────────┐
│ 1. PROBLEM & PRODUCT          │
│    Define the real problem    │
└──────────────┬────────────────┘
               ↓
┌───────────────────────────────┐
│ 2. REQUIREMENTS               │
│    Functional + Nonfunctional │
└──────────────┬────────────────┘
               ↓
┌───────────────────────────────┐
│ 3. SYSTEM ANALYSIS            │
│    Model real Chama processes │
└──────────────┬────────────────┘
               ↓
┌───────────────────────────────┐
│ 4. DOMAIN DESIGN              │
│    Business + financial rules │
└──────────────┬────────────────┘
               ↓
┌───────────────────────────────┐
│ 5. ARCHITECTURE DESIGN        │
│    Modules + providers        │
└──────────────┬────────────────┘
               ↓
┌───────────────────────────────┐
│ 6. DATABASE + API DESIGN      │
│    Schema + contracts         │
└──────────────┬────────────────┘
               ↓
┌───────────────────────────────┐
│ 7. IMPLEMENTATION              │
│    Build incrementally         │
└──────────────┬────────────────┘
               ↓
┌───────────────────────────────┐
│ 8. TESTING                    │
│    Unit + Integration + API   │
└──────────────┬────────────────┘
               ↓
┌───────────────────────────────┐
│ 9. SECURITY + AUDIT           │
└──────────────┬────────────────┘
               ↓
┌───────────────────────────────┐
│ 10. DEPLOYMENT                │
└──────────────┬────────────────┘
               ↓
┌───────────────────────────────┐
│ 11. MONITORING                │
└──────────────┬────────────────┘
               ↓
┌───────────────────────────────┐
│ 12. USER FEEDBACK             │
└──────────────┬────────────────┘
               │
               └──────────────→ NEXT VERSION

---

Final Principle

ChamaCore is developed one complete version at a time.

Each version must:

1. Solve a real problem.
2. Have explicit requirements.
3. Have understood business rules.
4. Have a deliberate data model.
5. Have a defined API contract.
6. Be implemented within the existing architecture.
7. Be tested.
8. Be secure enough for its stage.
9. Be deployable.
10. Produce feedback for the next version.

This keeps the project technically serious without turning it into unnecessary infrastructure engineering.
