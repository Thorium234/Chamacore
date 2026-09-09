Yes. And honestly, a Chama application is a better distributed-systems project for you than the generic banking system because you can model a real Kenyan problem while learning serious backend architecture.

But don't build "a Chama app" as just:

> members + contributions + balance + dashboard.



That's a glorified CRUD application.

Build a distributed Chama management and financial coordination platform.

The core idea

The fundamental domain is:

Chama
  ↓
Members
  ↓
Contributions
  ↓
Cycles
  ↓
Payouts
  ↓
Loans
  ↓
Repayments
  ↓
Ledger

The system should answer one question reliably:

> Who contributed what, when, why, and where did the money go?



Architecture

I would use Spring Boot and deliberately make it distributed:

Mobile App
                             │
                         Web App
                             │
                          USSD
                             │
                             ▼
                     ┌───────────────┐
                     │ API Gateway   │
                     └───────┬───────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
   Identity Service    Chama Service      Member Service
          │                  │                  │
          │                  ▼                  │
          │           Contribution Service      │
          │                  │                  │
          │                  ▼                  │
          │             Loan Service            │
          │                  │                  │
          └──────────────────┼──────────────────┘
                             ▼
                       Ledger Service
                             │
                             ▼
                           Kafka
                      ┌──────┼──────┐
                      ▼      ▼      ▼
                 Notification Audit Reporting

The services

I'd keep V1 to six services:

1. Identity Service

Handles:

Users
Authentication
JWT
Roles
Permissions

2. Chama Service

Handles:

Create chama
Chama profile
Chama rules
Meeting schedule
Contribution rules
Cycle configuration

3. Member Service

Handles:

Membership
Member status
Roles
Member profiles
Join/leave requests

4. Contribution Service

Handles:

Contributions
Expected contributions
Actual contributions
Contribution periods
Late contributions
Contribution history

5. Loan Service

Handles:

Loan applications
Approval
Disbursement
Repayment
Interest
Outstanding balance

6. Ledger Service

This is the one I would take extremely seriously.

It records the financial truth.

Transaction
Journal Entry
Debit
Credit
Account
Balance

Don't let every service invent its own balance calculation.


---

Where Kafka comes in

Suppose a member contributes KSh 5,000.

Don't make every service synchronously call every other service.

Instead:

Contribution Service
        │
        ▼
 ContributionRecorded
        │
        ▼
      Kafka
   ┌────┼─────┐
   ▼    ▼     ▼
Ledger Notification Reporting

The Ledger Service records the accounting event.

Notification Service sends an SMS/push notification.

Reporting Service updates analytical data.

This is where your project stops being CRUD.


---

Example

Member:

John

contributes:

KSh 5,000

The API might receive:

POST /api/v1/contributions

Contribution Service validates:

Is John a member?
Is the Chama active?
Is this contribution period open?
Is this payment already processed?

Then it creates the contribution and publishes:

ContributionRecorded

Kafka distributes the event.

Ledger Service receives it:

Debit
Cash/M-Pesa Account     5,000

Credit
Member Contribution    5,000

Notification Service:

"Your contribution of KSh 5,000 has been recorded."

Reporting Service:

John
Contributed: KSh 5,000

That's a legitimate distributed architecture.


---

Now add the rotating Chama cycle

This is where your application becomes interesting.

Imagine 10 members contribute:

KSh 5,000/month

Monthly pool:

10 × 5,000 = KSh 50,000

Then the Chama has a payout rotation:

January    → Member A
February   → Member B
March      → Member C
...

Your system needs to track:

Cycle
Contribution Period
Expected Amount
Actual Amount
Payout Order
Payout Status

Don't simply store:

member.balance

and call it accounting.

You need a transaction history from which balances can be derived and reconciled.


---

Then add loans

This gives you another excellent distributed workflow.

Member
   │
   ▼
Loan Application
   │
   ▼
Loan Service
   │
   ▼
Approval
   │
   ▼
Disbursement
   │
   ▼
Ledger
   │
   ▼
Repayments

Now introduce events:

LoanApproved
LoanDisbursed
RepaymentRecorded
LoanCompleted

And suddenly you have a proper event-driven system.


---

Your technology stack

I would make the stack:

Backend
Spring Boot

API
REST

Internal communication
gRPC

Event communication
Apache Kafka

Authentication
Spring Security + JWT

Database
PostgreSQL

Caching
Redis

Gateway
Spring Cloud Gateway

Containerization
Docker + Docker Compose

Testing
JUnit
Mockito
Testcontainers

Observability
OpenTelemetry
Prometheus
Grafana

Documentation
OpenAPI
Swagger

For the clients:

Web
Next.js

Mobile
React Native

USSD
Africa's Talking or another appropriate provider

Payments
Safaricom Daraja, subject to the current API requirements

The important thing is that the clients don't care how many microservices you have.

They see:

Chama API
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
        Web          Mobile        USSD

The internal architecture can evolve independently.


---

But here's my challenge to you

Do not start with 6 microservices.

That's the classic mistake.

You'll spend three weeks configuring infrastructure and almost no time building the actual product.

Start as a modular monolith:

chama-platform
│
├── identity
├── chama
├── member
├── contribution
├── loan
└── ledger

Get the domain right.

Then extract services deliberately:

Modular Monolith
       ↓
Extract Contribution Service
       ↓
Extract Ledger Service
       ↓
Introduce Kafka
       ↓
Introduce gRPC
       ↓
Introduce Gateway
       ↓
Distributed Chama Platform

That progression will teach you why distributed architecture exists rather than teaching you how to create six Docker containers.

And for your portfolio, I'd call the project something like ChamaCore and position it as:

> A distributed, event-driven Chama financial management platform built with Spring Boot, Kafka, gRPC, PostgreSQL and Docker.



That's a much stronger engineering project than "Chama Management System."
