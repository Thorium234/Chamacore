🇰🇪 Chama Management & Payment Platform

A production-oriented Chama management, financial management, payment and reconciliation platform designed for Kenyan Chamas.

The system allows Chamas to manage members, contributions, shares, loans, payouts and financial records while integrating with Kenyan payment and banking providers such as Jenga, KCB BUNI, NCBA and Safaricom Daraja.

The architecture is provider-agnostic. The Chama business logic must never depend directly on a specific bank or payment provider.

---

1. Project Vision

Traditional Chamas often manage:

- Member registration
- Monthly contributions
- Shares
- Loans
- Loan repayments
- Payouts
- Bank deposits
- M-Pesa payments
- Financial records

using books, spreadsheets, WhatsApp messages and manual reconciliation.

This project aims to provide one system where:

Member
   ↓
Contribution
   ↓
Payment
   ↓
Payment Provider
   ↓
M-Pesa / Bank
   ↓
Confirmation
   ↓
Reconciliation
   ↓
Chama Ledger

The goal is not simply to build CRUD screens.

The goal is to build a real financial system with proper transaction tracking, reconciliation, auditability and provider integrations.

---

2. Core Principle

The Chama system must not depend on one payment provider.

Bad architecture:

ContributionService
       ↓
Jenga
       ↓
Equity

Better architecture:

ContributionService
       ↓
PaymentProviderService
       ↓
Provider Resolver
       │
       ├── Jenga
       ├── KCB BUNI
       ├── NCBA
       └── Daraja

This allows a Chama using Equity to use Jenga while another Chama using KCB can use KCB BUNI.

The business layer does not need to change.

---

3. Technology Stack

Backend

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Pydantic
- JWT authentication
- REST API

External integrations

- Jenga API
- KCB BUNI
- NCBA APIs / collection services
- Safaricom Daraja

Frontend

Planned:

- React
- React Native

Future

- USSD
- SMS
- Background workers
- Notifications
- Reporting
- Monitoring

---

4. High-Level Architecture

                     ┌──────────────────────┐
                     │     React Web        │
                     └──────────┬───────────┘
                                │
                     ┌──────────▼───────────┐
                     │   React Native App   │
                     └──────────┬───────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │       FastAPI        │
                     │      REST API        │
                     └──────────┬───────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
          ▼                     ▼                     ▼
 ┌────────────────┐    ┌──────────────────┐   ┌───────────────┐
 │ Chama Domain   │    │ Payment Service  │   │ Bank Service  │
 │                │    │                  │   │               │
 │ Members        │    │ Provider         │   │ Balance       │
 │ Contributions  │    │ Resolution       │   │ Statements    │
 │ Shares         │    │ Payment Status   │   │ Transactions  │
 │ Loans          │    │ Webhooks         │   │ Reconciliation│
 │ Payouts        │    │ Reconciliation   │   │               │
 └────────────────┘    └────────┬─────────┘   └───────────────┘
                                │
             ┌──────────────────┼──────────────────┐
             │                  │                  │
             ▼                  ▼                  ▼
          Jenga             KCB BUNI             NCBA
             │                  │                  │
          Equity              KCB               NCBA
             │
          M-Pesa

                         +
                       Daraja
                         │
                      M-Pesa

---

5. Main Modules

The system is divided into the following domains.

1. Authentication
2. Chama Management
3. Member Management
4. Contributions
5. Shares
6. Loans
7. Loan Repayments
8. Payouts
9. Ledger
10. Payments
11. Payment Providers
12. Bank Accounts
13. Reconciliation
14. Notifications
15. Reports
16. Audit
17. USSD

These will be implemented incrementally.

---

6. Development Roadmap

V1 - Chama Foundation

Build the basic Chama management system.

Chama

- Create Chama
- Update Chama
- View Chama
- Delete/deactivate Chama
- Chama profile
- Contribution rules

Members

- Register member
- Add member
- Update member
- Remove/deactivate member
- View member
- Member history

Roles

CHAIRPERSON
TREASURER
SECRETARY
MEMBER

Registration Fee

Track:

Member
Registration Fee
Payment Status
Date

Contributions

Initially record contributions manually.

Member
   ↓
Contribution
   ↓
Amount
   ↓
Month

No payment provider integration yet.

---

7. V2 - Financial Management

Introduce the financial domain.

Contributions

Contribution
├── Member
├── Chama
├── Amount
├── Period
├── Status
└── Date

Shares

Track:

Member
   ↓
Shares
   ↓
Share Value

Loans

Loan
├── Member
├── Principal
├── Interest
├── Total Due
├── Status
└── Due Date

Loan Repayments

Loan
   ↓
Loan Repayment
   ↓
Payment

Payouts

Track money leaving the Chama.

---

8. Financial Ledger

The application must not rely on a manually modified:

balance = 100000

Instead, financial activity must be represented by transactions.

Example:

John Contribution       +1,000
Mary Contribution       +1,000
Loan to John            -5,000
Loan repayment          +2,000
--------------------------------
Current balance         -1,000

The ledger becomes the financial source of truth.

---

9. V3 - Payment Architecture

Introduce a provider-independent payment system.

Payment entities

Payment
PaymentAttempt
ProviderTransaction
ProviderCallback
PaymentProviderConfiguration

Payment states

PENDING
PROCESSING
COMPLETED
FAILED
CANCELLED
REVERSED
UNKNOWN

---

10. PaymentProvider Interface

The application should define an internal interface.

Conceptually:

PaymentProvider
│
├── initiate_payment()
├── get_payment_status()
├── handle_callback()
├── verify_transaction()
├── refund_payment()
└── reconcile()

Provider implementations:

PaymentProvider
│
├── JengaPaymentProvider
├── KCBPaymentProvider
├── NCBAPaymentProvider
└── DarajaPaymentProvider

The rest of the application communicates only with the interface.

---

11. BankProvider Interface

Payments and bank-account services are separate concepts.

Define:

BankProvider
│
├── get_balance()
├── get_transactions()
├── get_statement()
├── validate_account()
└── reconcile()

Implementations:

BankProvider
│
├── JengaBankProvider
├── KCBBankProvider
└── NCBABankProvider

This prevents the payment system from becoming tightly coupled to banking APIs.

---

12. Provider Coverage

The system is designed to support:

Provider| Primary purpose
Jenga| Payment processing + supported bank services
KCB BUNI| Payments, interoperability and KCB services
NCBA| Collections, payment notifications and banking integrations
Daraja| Direct M-Pesa integration

Important

Provider capability is not assumed to be universal.

For example, Jenga's documentation currently identifies Equity for its documented Account Services.

KCB BUNI provides APIs across multiple payment networks and has KCB/VOOMA requirements for production usage.

NCBA provides its own collection and API integration products.

Therefore, provider selection is based on the specific capability required by the Chama, not simply the bank name.

---

13. V4 - Jenga Integration

The first major payment integration will be Jenga.

For an Equity Chama:

Member
   ↓
FastAPI
   ↓
PaymentProviderService
   ↓
JengaPaymentProvider
   ↓
Jenga API
   ↓
M-Pesa STK Push
   ↓
Member enters PIN
   ↓
Payment
   ↓
Jenga Callback
   ↓
FastAPI
   ↓
Payment Completed
   ↓
Contribution Paid
   ↓
Ledger Updated

Jenga supports M-Pesa STK/USSD Push and documents account-based settlement.

---

14. V5 - Webhooks

Every provider gets its own webhook endpoint.

POST /webhooks/jenga
POST /webhooks/kcb
POST /webhooks/ncba
POST /webhooks/daraja

Provider-specific payloads are converted into one internal format.

Example:

{
  "provider": "jenga",
  "provider_transaction_id": "ABC123",
  "payment_reference": "P7K92A",
  "amount": 1000,
  "currency": "KES",
  "status": "COMPLETED"
}

The internal system then processes:

Webhook
   ↓
Provider Adapter
   ↓
Normalized Event
   ↓
Payment Service
   ↓
Reconciliation
   ↓
Ledger

---

15. Idempotency

Financial callbacks can potentially be delivered more than once.

The system must never credit a payment twice.

Example:

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

Database constraints should include:

UNIQUE(provider, provider_transaction_id)

---

16. Payment References

Every payment receives an internal reference.

Example:

P7K92A

Database mapping:

P7K92A
   ↓
Payment UUID
   ↓
Contribution
   ↓
Member
   ↓
Chama

The external provider reference and internal database ID must remain separate.

---

17. V6 - KCB BUNI

Implement:

KCBPaymentProvider

and:

KCBBankProvider

Structure:

providers/
└── kcb/
    ├── client.py
    ├── auth.py
    ├── payments.py
    ├── accounts.py
    ├── callbacks.py
    └── mapper.py

Flow:

KCB Chama
   ↓
KCB Bank Account
   ↓
KCB BUNI
   ↓
FastAPI
   ↓
Payment / Banking Service

The KCB integration must only expose capabilities actually available to the application's KCB account and approved BUNI products.

---

18. V7 - NCBA

Implement:

NCBAPaymentProvider
NCBABankProvider

Structure:

providers/
└── ncba/
    ├── client.py
    ├── auth.py
    ├── payments.py
    ├── collections.py
    ├── accounts.py
    ├── callbacks.py
    └── mapper.py

NCBA's collection/API products are particularly useful for automatic payment notification and reconciliation.

---

19. V8 - Daraja

Implement a direct M-Pesa provider.

DarajaPaymentProvider

Structure:

providers/
└── daraja/
    ├── client.py
    ├── auth.py
    ├── stk.py
    ├── c2b.py
    ├── callbacks.py
    └── mapper.py

This gives the platform another option when a Chama wants direct Safaricom M-Pesa integration rather than a bank/provider intermediary.

---

20. Provider Resolution

When a member makes a payment:

POST /api/v1/contributions/{id}/pay

FastAPI determines:

Which Chama?
       ↓
Which bank?
       ↓
Which provider?
       ↓
Which payment method?

Example:

NUCSWG
   ↓
Equity
   ↓
Jenga
   ↓
M-Pesa STK

Another Chama:

XYZ Chama
   ↓
KCB
   ↓
KCB BUNI
   ↓
Supported payment method

---

21. V9 - Reconciliation Engine

Reconciliation connects external transactions to internal financial records.

Example:

Internal:

Contribution #543
John
KSh 1,000

External:

Provider Transaction

ABC123
KSh 1,000
COMPLETED

Reconciliation:

ABC123
   ↓
Payment #900
   ↓
Contribution #543
   ↓
John
   ↓
Ledger

Never match payments only using:

amount == 1000

Use:

provider
provider_transaction_id
payment_reference
amount
timestamp
status

---

22. V10 - Bank Reconciliation

Payment confirmation and bank confirmation are separate.

Payment event

M-Pesa
   ↓
Provider
   ↓
Payment confirmed

Bank event

Bank
   ↓
Account transaction
   ↓
Bank statement/API

Where supported:

Bank API
   ↓
BankTransaction
   ↓
ReconciliationService
   ↓
Internal Ledger

This allows the system to compare:

Provider transactions
        VS
Bank transactions
        VS
Chama ledger

---

23. V11 - Reports

Provide:

Member statement

Member
├── Contributions
├── Shares
├── Loans
├── Repayments
└── Balance

Chama statement

Opening Balance
+ Contributions
+ Loan Repayments
- Loans
- Payouts
= Closing Balance

Financial reports

- Monthly contributions
- Member contributions
- Loan report
- Loan repayment report
- Payout report
- Provider transaction report
- Bank reconciliation report
- Outstanding contributions
- Outstanding loans

---

24. V12 - Audit System

Every sensitive financial operation should produce an audit event.

Example:

Treasurer
   ↓
Approved Loan
   ↓
Audit Log

Store:

user
action
entity
entity_id
old_value
new_value
timestamp
IP/device information where appropriate

Examples:

MEMBER_CREATED
CONTRIBUTION_CREATED
PAYMENT_INITIATED
PAYMENT_COMPLETED
LOAN_APPROVED
LOAN_REPAID
PAYOUT_CREATED
BANK_TRANSACTION_RECONCILED

---

25. V13 - Notifications

Add:

SMS
Email
Push Notifications

Examples:

Contribution received
Payment failed
Loan approved
Loan repayment due
Monthly contribution reminder
Payout completed

Notifications should be handled asynchronously rather than blocking the payment request.

---

26. V14 - React Web Application

The web application is primarily for executives.

Dashboard:

┌──────────────────────────────────┐
│ Chama Dashboard                  │
├──────────────────────────────────┤
│ Members              32          │
│ Contributions       45,000       │
│ Loans               18,000       │
│ Balance             127,500      │
└──────────────────────────────────┘

Main sections:

Dashboard
Members
Contributions
Shares
Loans
Payouts
Payments
Bank Account
Reconciliation
Reports
Audit
Settings

---

27. V15 - React Native Application

The mobile application is primarily for members.

Members can:

View contributions
Make contribution
View shares
Request loan
View loan
Make repayment
View statements
Receive notifications

The mobile app communicates with the same FastAPI backend.

React Native
      ↓
FastAPI
      ↓
PostgreSQL

---

28. V16 - USSD

The same backend can support USSD.

Example:

*XXXX#
   ↓
1. My Account
2. Contribution
3. Loan
4. Balance
5. Statement

The architecture becomes:

React
   │
React Native
   │
USSD
   │
   ▼
FastAPI
   │
   ▼
Chama Services

The business logic remains shared.

---

29. Backend Project Structure

app/
│
├── api/
│   ├── auth/
│   ├── chamas/
│   ├── members/
│   ├── contributions/
│   ├── shares/
│   ├── loans/
│   ├── payouts/
│   ├── payments/
│   ├── reports/
│   └── webhooks/
│
├── domain/
│   ├── chamas/
│   ├── members/
│   ├── contributions/
│   ├── shares/
│   ├── loans/
│   ├── payments/
│   └── ledger/
│
├── services/
│   ├── chama_service.py
│   ├── member_service.py
│   ├── contribution_service.py
│   ├── share_service.py
│   ├── loan_service.py
│   ├── ledger_service.py
│   ├── payment_service.py
│   └── reconciliation_service.py
│
├── providers/
│   │
│   ├── base/
│   │   ├── payment_provider.py
│   │   └── bank_provider.py
│   │
│   ├── jenga/
│   │   ├── client.py
│   │   ├── auth.py
│   │   ├── payments.py
│   │   ├── accounts.py
│   │   ├── callbacks.py
│   │   └── mapper.py
│   │
│   ├── kcb/
│   │   ├── client.py
│   │   ├── auth.py
│   │   ├── payments.py
│   │   ├── accounts.py
│   │   ├── callbacks.py
│   │   └── mapper.py
│   │
│   ├── ncba/
│   │   ├── client.py
│   │   ├── auth.py
│   │   ├── payments.py
│   │   ├── collections.py
│   │   ├── accounts.py
│   │   ├── callbacks.py
│   │   └── mapper.py
│   │
│   └── daraja/
│       ├── client.py
│       ├── auth.py
│       ├── stk.py
│       ├── c2b.py
│       ├── callbacks.py
│       └── mapper.py
│
├── models/
├── schemas/
├── repositories/
├── db/
├── security/
├── workers/
├── config/
└── main.py

---

30. Database Structure

Core tables:

users
chamas
memberships
roles

contributions
shares

loans
loan_repayments

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

Important relationships:

Member
   ↓
Contribution
   ↓
Payment
   ↓
ProviderTransaction
   ↓
LedgerEntry

Bank side:

BankAccount
   ↓
BankTransaction
   ↓
ReconciliationRecord
   ↓
LedgerEntry

---

31. Security

The production system must implement:

- Authentication
- JWT/session security
- Password hashing
- Role-based access control
- Provider credential encryption
- HTTPS
- Input validation
- Rate limiting
- Webhook verification
- Idempotency
- Audit logs
- Database backups
- Secrets management
- Secure environment variables

Never store:

API secrets
Consumer secrets
Passwords
M-Pesa credentials
Bank credentials

directly in source code.

---

32. Financial Rules

Financial operations must be treated differently from ordinary CRUD.

Do not allow:

DELETE payment

after a successful financial transaction.

Instead use:

REVERSAL

or:

REFUND

where supported.

Likewise, historical ledger entries should be immutable.

Corrections should create new transactions rather than silently modifying financial history.

---

33. Testing Strategy

Unit tests

Test:

ContributionService
LoanService
LedgerService
PaymentService
ReconciliationService

Integration tests

Test:

FastAPI
   ↓
PostgreSQL

Provider tests

Use provider sandboxes where available.

Jenga Sandbox
KCB BUNI Sandbox
Daraja Sandbox

Webhook tests

Test:

SUCCESS
FAILED
PENDING
CANCELLED
DUPLICATE
UNKNOWN

Financial tests

Especially test:

1000 contribution
1000 duplicate callback
1000 reversal
500 partial payment
multiple contributions
loan + repayment

---

34. Deployment

Initial deployment:

FastAPI
   ↓
Linux VPS / Cloud
   ↓
PostgreSQL

Production components can later include:

Reverse Proxy
Application Server
PostgreSQL
Redis
Background Worker
Monitoring
Logging
Backup System

Do not introduce these unnecessarily in V1.

Add them when the application actually requires them.

---

35. Development Phases

The project should be built in this order:

Phase 1
│
├── Requirements
├── Domain modelling
└── Database design

Phase 2
│
├── FastAPI
├── PostgreSQL
├── Authentication
└── Chama CRUD

Phase 3
│
├── Members
├── Roles
├── Contributions
└── Shares

Phase 4
│
├── Loans
├── Repayments
├── Payouts
└── Ledger

Phase 5
│
├── Payment model
├── PaymentProvider interface
└── Provider resolver

Phase 6
│
└── Jenga integration

Phase 7
│
├── Webhooks
├── Idempotency
└── Payment reconciliation

Phase 8
│
├── KCB BUNI
└── NCBA

Phase 9
│
├── Daraja
└── Additional providers

Phase 10
│
├── Bank reconciliation
├── Statements
└── Reports

Phase 11
│
├── React
├── React Native
└── USSD

Phase 12
│
├── Security hardening
├── Monitoring
├── Backups
└── Production deployment

---

36. Provider Abstraction Goal

The ultimate goal is that this code:

payment_service.collect(
    chama_id=chama_id,
    member_id=member_id,
    contribution_id=contribution_id,
    amount=1000
)

does not care whether the Chama uses:

Jenga
KCB BUNI
NCBA
Daraja

The provider layer handles that complexity.

                 PaymentService
                       │
                       ▼
               ProviderResolver
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       Jenga          KCB          NCBA
                       │
                    BUNI
                       
                       +
                    Daraja

---

37. Example Complete Payment

John
 │
 │ KSh 1,000
 ▼
React Native
 │
 ▼
POST /contributions/543/pay
 │
 ▼
FastAPI
 │
 ▼
ContributionService
 │
 ▼
PaymentService
 │
 ▼
ProviderResolver
 │
 ▼
JengaPaymentProvider
 │
 ▼
Jenga
 │
 ▼
M-Pesa STK
 │
 ▼
John enters PIN
 │
 ▼
M-Pesa
 │
 ▼
Jenga
 │
 ▼
POST /webhooks/jenga
 │
 ▼
Webhook Handler
 │
 ▼
Verify + Idempotency
 │
 ▼
Payment COMPLETED
 │
 ▼
Contribution PAID
 │
 ▼
Ledger Entry +1,000
 │
 ▼
Member Statement Updated

---

38. What We Are NOT Building Initially

To avoid overengineering, V1 will not start with:

- Microservices
- Kafka
- gRPC
- Kubernetes
- Complex event sourcing infrastructure
- Multiple databases
- Artificially distributed services

The initial backend is:

FastAPI
+
PostgreSQL
+
Modular architecture

External providers are integrated behind clean interfaces.

If the platform eventually reaches a scale where individual services need to be separated, that can be done later.

---

39. Definition of Success

The first major milestone is not "we have a dashboard."

The first meaningful end-to-end milestone is:

Chama created
      ↓
Member registered
      ↓
Contribution created
      ↓
Member clicks Pay
      ↓
M-Pesa STK
      ↓
Member enters PIN
      ↓
Provider confirms payment
      ↓
Webhook received
      ↓
Payment reconciled
      ↓
Contribution marked paid
      ↓
Ledger updated
      ↓
Member statement updated

Once that works reliably, the platform has a real financial transaction pipeline.

---

40. Final Architecture

                         CHAMA PLATFORM
                               │
                               ▼
                     ┌──────────────────┐
                     │     FastAPI      │
                     └────────┬─────────┘
                              │
          ┌───────────────────┼────────────────────┐
          │                   │                    │
          ▼                   ▼                    ▼
    Chama Domain        Payment Service       Bank Service
          │                   │                    │
          │                   ▼                    │
          │            Provider Resolver           │
          │                   │                    │
          │       ┌───────────┼───────────┐        │
          │       │           │           │        │
          │       ▼           ▼           ▼        │
          │     Jenga       KCB BUNI     NCBA      │
          │       │           │           │        │
          │       ▼           ▼           ▼        │
          │    Equity        KCB         NCBA      │
          │       │                              │
          │       ▼                              │
          │    M-Pesa                            │
          │                                      │
          └──────────────────┬───────────────────┘
                             ▼
                       PostgreSQL
                             │
                             ▼
                     Financial Ledger

---

41. Project Philosophy

The project follows five principles:

1. Domain first

Understand the Chama's actual financial processes before writing code.

2. Financial correctness

Money movement must be traceable and auditable.

3. Provider independence

Banks and payment providers are integrations, not the core business logic.

4. Incremental development

Build one working version at a time.

5. Production thinking without premature complexity

Use proper architecture from the beginning, but do not introduce infrastructure that the current scale does not need.

---

Current Target

The immediate implementation target is:

V1
Chama
Members
Roles
Contributions
Shares
        ↓
V2
Loans
Repayments
Payouts
Ledger
        ↓
V3
PaymentProvider abstraction
        ↓
V4
Jenga + M-Pesa STK
        ↓
V5
Webhooks + Reconciliation
        ↓
V6
KCB BUNI
        ↓
V7
NCBA
        ↓
V8
Daraja
        ↓
V9+
Bank reconciliation
Reports
React
React Native
USSD
Production hardening

The first coding task should therefore be V1 domain modelling and database design, not the Jenga integration. The payment layer should be designed before the first provider is implemented, so Jenga becomes the first adapter rather than the foundation of the entire system.
