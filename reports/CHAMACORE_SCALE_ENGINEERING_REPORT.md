# ChamaCore Engineering Scale Report

## Purpose

This document is a development report for the next stage of ChamaCore.

The goal is **not to rewrite ChamaCore**.

The goal is to take the existing system, preserve the architecture and
working financial logic, remove dangerous inconsistencies, finish the
missing financial domain, and make the project easier to extend safely.

The developer receiving this document is responsible for implementation.

This document deliberately contains **no implementation code**. It
defines what should be done, why it matters, what must not be disturbed,
and what completion should mean.

------------------------------------------------------------------------

# 1. Core Directive

## Do not refactor everything

ChamaCore already has a meaningful architecture.

Do not replace the architecture simply because another pattern looks
cleaner.

Do not introduce microservices.

Do not rewrite the database layer.

Do not replace FastAPI.

Do not replace SQLAlchemy.

Do not replace the ledger.

Do not rewrite working payment flows.

Do not rename large parts of the project for cosmetic reasons.

Do not perform broad refactoring without a concrete defect, scalability
requirement, security requirement, or maintainability problem.

The correct strategy is:

> **Preserve what works. Strengthen what is weak. Complete what is
> missing.**

Every change should answer at least one of these questions:

1.  Does it fix an actual defect?
2.  Does it close a known financial or security risk?
3.  Does it complete an incomplete business workflow?
4.  Does it improve scalability without changing established behavior?
5.  Does it make future development safer?
6.  Does it make the documented architecture match the real system?

If the answer is no, the change probably does not belong in this phase.

------------------------------------------------------------------------

# 2. Current Engineering Position

ChamaCore has already moved beyond a basic CRUD application.

The repository contains substantial work around:

-   FastAPI application structure
-   Pydantic schemas
-   application/service logic
-   repository boundaries
-   SQLAlchemy 2.x
-   Alembic migrations
-   authentication and authorization
-   Chama and membership management
-   contributions
-   financial ledger
-   double-entry accounting concepts
-   immutable financial history
-   idempotency
-   compensating reversals
-   payment abstractions
-   Daraja integration
-   C2B handling
-   STK payment flows
-   webhook handling
-   structured logging
-   request IDs
-   metrics
-   rate limiting
-   health/readiness checks
-   PostgreSQL testing
-   SQLite development support
-   Docker and deployment documentation

This means the next stage should not be another infrastructure
accumulation phase.

The priority should now be **domain completion, consistency,
reliability, and controlled scale**.

------------------------------------------------------------------------

# 3. First Priority: Make Project Documentation Agree With Reality

The repository currently contains documentation that does not completely
describe the same project state.

The project has progressed into payment functionality, while some
development instructions and roadmap language still describe an earlier
stage.

This is dangerous because the documentation is part of the engineering
system.

A developer or coding agent must not have to guess which document is
authoritative.

## Required action

Update the following documents so they describe the same current state:

-   `AGENTS.md`
-   `README.md`
-   project status documentation
-   roadmap documentation
-   architecture documentation
-   relevant ADR documentation

The documents should clearly distinguish:

``` text
COMPLETED

CURRENT WORK

NEXT WORK

DEFERRED

OUT OF SCOPE
```

Do not rewrite the historical record.

Completed work should remain documented as completed.

The roadmap should describe future work rather than pretending already
implemented functionality is still pending.

## Acceptance condition

A new developer should be able to read the repository documentation and
answer:

-   What is already implemented?
-   What is currently being developed?
-   What is deliberately deferred?
-   What must not be changed?
-   Which business decisions are still unresolved?
-   Which tests are active?
-   Which tests are intentionally deferred?

without inspecting the entire codebase.

------------------------------------------------------------------------

# 4. Protect the Financial Core

The financial ledger is one of the most important architectural
decisions in ChamaCore.

Do not simplify it into ordinary mutable balances.

Do not introduce shortcuts that bypass the ledger.

Do not allow business modules to independently invent financial truth.

The ledger must remain the authoritative financial record.

## Rules

Financial events should produce appropriate ledger transactions.

Historical posted financial records should not be silently edited or
deleted.

Corrections should use controlled compensating transactions.

Balances should be derived from authoritative financial records.

Business modules must not maintain competing financial truths unless
there is a documented reason and reconciliation mechanism.

## Developer instruction

Before changing anything involving:

-   contributions
-   shares
-   registration fees
-   payments
-   loans
-   repayments
-   payouts
-   reversals
-   financial statements

first determine how the change interacts with the existing ledger.

If the proposed implementation bypasses the ledger, stop and review the
design before proceeding.

------------------------------------------------------------------------

# 5. Complete the Financial Domain Before Adding More Infrastructure

The major remaining work is not another framework or service.

The missing business domain must be completed.

The priority areas are:

1.  Registration fee accounting
2.  Loans
3.  Loan repayments
4.  Payouts
5.  Financial reporting
6.  Audit events

These areas should be completed in a controlled sequence.

------------------------------------------------------------------------

# 6. Registration Fee Accounting

Registration fees should not remain an isolated membership concept if
they represent real financial activity.

Define clearly:

-   when the fee becomes financially recognized
-   how payment is recorded
-   which account receives the amount
-   whether the fee is refundable
-   what happens when membership registration is cancelled
-   how reversals are handled
-   how the fee appears in member statements
-   how it appears in Chama financial reports

The implementation must use the existing financial architecture rather
than creating a separate accounting mechanism.

## Acceptance condition

A registration fee should have a complete and auditable lifecycle from
creation or obligation through payment and, where applicable, reversal.

------------------------------------------------------------------------

# 7. Loans Must Be Designed Before They Are Coded

Loans are a core Chama feature, but they must not be implemented as
ordinary CRUD records.

A loan is a financial lifecycle.

Before implementation, the business rules must explicitly answer:

-   Who can apply?
-   Who can approve?
-   Can a member have multiple active loans?
-   What determines the borrowing limit?
-   Is the limit based on shares, contributions, guarantors, or another
    rule?
-   What interest model is used?
-   Is interest flat or reducing balance?
-   When does interest start accruing?
-   What repayment schedule is used?
-   What happens when a repayment is late?
-   Are penalties supported?
-   Can a loan be restructured?
-   Can a loan be written off?
-   What happens when a member exits while owing money?
-   How are partial repayments allocated?
-   How are principal, interest, penalties, and fees separated?
-   Can a loan be cancelled before disbursement?
-   What happens if approval occurs but disbursement fails?

Do not let a developer or coding agent invent these rules.

Unresolved business questions must remain explicit until decided.

## Required lifecycle

The eventual design should clearly represent the loan lifecycle:

``` text
Application
    ↓
Review
    ↓
Approval or Rejection
    ↓
Disbursement
    ↓
Outstanding Loan
    ↓
Repayment
    ↓
Completion
```

Every financially meaningful transition must have a defined accounting
consequence.

------------------------------------------------------------------------

# 8. Loan Repayments

Repayments must not simply reduce a numeric loan balance.

They must be treated as financial events.

The system needs clear rules for allocating repayment amounts.

For example, the business rules may eventually define an order such as:

``` text
Penalties
Interest
Fees
Principal
```

But the actual order must be decided by the business and documented
before implementation.

Do not assume the allocation order.

## Required behavior

The system must be able to explain:

> Where did this repayment go?

A developer, auditor, or member should be able to trace the repayment to
the affected financial components.

Partial payments must be supported if the business rules allow them.

Overpayments must have an explicit policy.

Failed payments must not create false repayment records.

Duplicate provider callbacks must not create duplicate financial
effects.

------------------------------------------------------------------------

# 9. Payouts

Payouts need the same level of financial discipline as contributions.

Define:

-   who can request a payout
-   who can approve it
-   what qualifies for payout
-   whether payout limits exist
-   which account is affected
-   how payout approval differs from actual disbursement
-   how failed disbursements are handled
-   how reversals work
-   whether a payout can be cancelled
-   how the payout appears in statements and reports

Do not treat payout status as proof that money moved.

A business state and a financial settlement are related but not
identical.

The system should distinguish between:

``` text
Requested
Approved
Financially recorded
Disbursed
Confirmed
Failed
Reversed
```

The exact state model should follow the final business rules.

------------------------------------------------------------------------

# 10. Payment System: Strengthen, Do Not Rewrite

The payment architecture should be preserved.

The existing provider abstraction is useful because ChamaCore should not
become permanently coupled to one payment provider.

Do not rewrite the payment system simply to make it look cleaner.

Instead strengthen it around real operational risks.

## Required review areas

Verify:

-   idempotency
-   duplicate callbacks
-   callback replay
-   payment attempt state transitions
-   failed provider requests
-   delayed callbacks
-   unexpected callback order
-   provider transaction references
-   reconciliation
-   transaction-to-member mapping
-   transaction-to-Chama mapping
-   transaction-to-financial-event mapping

The key question is:

> Can the same provider event safely arrive more than once?

The answer must be yes.

The financial result must remain correct.

------------------------------------------------------------------------

# 11. Live Provider Integration

The repository has substantial mocked and contract-level payment
testing.

That is useful, but it is not equivalent to real provider integration.

Do not claim full production provider verification until live sandbox or
equivalent integration testing has been performed.

The development process should distinguish:

``` text
Unit tests
Contract tests
Mock provider tests
Integration tests
Live sandbox tests
Production monitoring
```

Each provides different evidence.

The developer should add live integration testing when the required
provider credentials and environment are available.

Secrets must never be committed to the repository.

------------------------------------------------------------------------

# 12. Deferred Tests Must Become Explicit Work Items

The repository currently has tests that are intentionally deferred.

Do not silently leave them that way.

For every deferred test, document:

-   test name
-   why it is deferred
-   what environment it requires
-   whether it is a local-only test
-   whether CI should execute it
-   what condition allows it to be re-enabled

The project status should distinguish:

``` text
Collected tests
Active passing tests
Deferred tests
Failed tests
```

Do not count deferred tests as evidence that the feature is fully
protected.

## Acceptance condition

Every deferred test has an explicit reason and a known path to
activation.

------------------------------------------------------------------------

# 13. PostgreSQL Should Be the Important Integration Target

SQLite is useful during development.

Keep it.

There is no need to remove SQLite.

However, PostgreSQL is the production database and should remain the
authoritative integration environment for behavior that depends on
database-specific guarantees.

Pay particular attention to:

-   transactions
-   concurrency
-   locking
-   constraints
-   triggers
-   indexes
-   uniqueness
-   isolation behavior
-   financial consistency

Do not weaken PostgreSQL-specific protections merely to make SQLite
behave identically.

If a behavior genuinely differs between the two databases, document the
difference.

------------------------------------------------------------------------

# 14. Identity and Account Claiming Need Security Review

The member identity model contains sensitive identity information.

The account-claiming process therefore deserves a security-focused
review.

Do not expose sensitive identity fields through ordinary responses.

Review:

-   account claiming
-   phone verification
-   failed attempts
-   rate limiting
-   enumeration resistance
-   audit logging
-   account takeover scenarios
-   identity re-verification
-   handling of government identification information

The important question is not simply:

> Does a legitimate member successfully claim an account?

The important question is also:

> Can an attacker successfully claim somebody else's account?

Do not add more identity information to the API merely because it makes
development easier.

------------------------------------------------------------------------

# 15. Audit Events Are Not the Same as Application Logs

Do not solve auditing by adding more log messages.

There are at least three different concepts:

``` text
Application log
Financial transaction
Business audit event
```

An application log answers:

> What did the software do?

A financial transaction answers:

> What financial event occurred?

An audit event answers:

> Who performed which business action, when, against what object, and
> what changed?

ChamaCore should eventually support a proper business audit trail for
sensitive operations.

Examples include:

-   membership role changes
-   approval actions
-   loan approval
-   payout approval
-   payment reconciliation
-   financial reversals
-   administrative changes
-   account security events

Do not duplicate every application log as an audit event.

Audit events should represent meaningful business actions.

------------------------------------------------------------------------

# 16. Reporting Should Be Derived From Authoritative Data

Do not build reports by maintaining another set of manually updated
balances.

Reports should be derived from authoritative records.

Important future reports include:

-   member statement
-   contribution statement
-   share statement
-   loan statement
-   repayment history
-   payout history
-   Chama financial summary
-   income and expense information where applicable
-   outstanding loans
-   financial transaction history

Every report should have a clear definition of its source data.

If a report displays a balance, the developer must be able to explain
exactly how that balance is calculated.

------------------------------------------------------------------------

# 17. Scalability Strategy

ChamaCore should scale incrementally.

Do not prematurely introduce:

-   microservices
-   event-driven infrastructure everywhere
-   Kafka
-   distributed databases
-   service meshes
-   Kubernetes
-   multiple independently deployed backends

None of those should be introduced merely because the project is
growing.

First scale the existing architecture.

Focus on:

-   database indexes
-   efficient queries
-   pagination
-   avoiding unnecessary database round trips
-   transaction boundaries
-   connection management
-   background processing where genuinely necessary
-   caching only where measurement shows it is useful
-   structured observability
-   rate limiting
-   efficient webhook processing
-   reliable retry behavior

Measure before introducing infrastructure.

------------------------------------------------------------------------

# 18. Keep the Modular Monolith

The modular monolith should remain the architectural center.

The system can contain strong internal boundaries without becoming
multiple services.

Conceptually:

``` text
Auth
Membership
Chama
Contributions
Ledger
Payments
Loans
Payouts
Reporting
Audit
```

These should remain logically separated modules.

They do not need to become separately deployed services.

The objective is to make future extraction possible if actual scale
requires it, without paying the distributed-systems cost today.

------------------------------------------------------------------------

# 19. Service Boundaries Must Stay Clear

When adding a new feature, do not allow route handlers to become
business logic containers.

The existing separation between:

``` text
API
Schemas
Application logic
Repositories
Database models
```

should be preserved.

A new feature should fit into that structure rather than bypassing it.

If an existing boundary is genuinely causing a problem, document the
problem before changing the boundary.

------------------------------------------------------------------------

# 20. Database Changes Must Be Deliberate

Every schema change should have:

-   an Alembic migration
-   a documented reason
-   backward compatibility considerations where relevant
-   appropriate indexes
-   constraint considerations
-   test coverage
-   rollback considerations

Do not edit the database manually and then try to make migrations catch
up.

The migration history is part of the system.

------------------------------------------------------------------------

# 21. API Compatibility

Avoid breaking existing API behavior unnecessarily.

When changing an existing endpoint, first determine:

-   who uses it
-   whether the response shape is public
-   whether existing clients depend on it
-   whether database behavior changes
-   whether authentication behavior changes

Prefer additive changes where practical.

If a breaking change is unavoidable, document it clearly.

Do not silently change financial API semantics.

------------------------------------------------------------------------

# 22. Idempotency Is Mandatory for Financial Side Effects

Any operation that can create a financial effect must be evaluated for
duplicate requests.

Examples:

-   contribution confirmation
-   payment settlement
-   loan disbursement
-   repayment
-   payout
-   reversal

A retry must not create a second financial effect.

Idempotency must be tied to a meaningful business or provider reference.

Do not rely solely on application memory.

The database should provide the final protection against duplicate
financial records.

------------------------------------------------------------------------

# 23. Concurrency Must Be Treated as a Real Requirement

Do not assume users operate sequentially.

Potential concurrent situations include:

``` text
Two membership requests
Two payment callbacks
Two repayment requests
Two administrators approving an action
Two processes updating the same financial state
```

The application should rely on database guarantees where appropriate.

Race conditions should be tested explicitly.

A test that passes with one request is not sufficient evidence for a
financial operation.

------------------------------------------------------------------------

# 24. Error Handling Must Preserve Financial Truth

A failed request must not leave a partially recorded financial event.

Review transaction boundaries around every financial operation.

The developer must be able to answer:

> What happens if the application crashes halfway through this
> operation?

For every financial workflow, define the expected result if:

-   validation fails
-   database transaction fails
-   provider request fails
-   provider responds slowly
-   provider callback arrives late
-   callback arrives twice
-   callback arrives before another expected event
-   application crashes during processing

This should be addressed through the existing transaction and state
architecture rather than through ad hoc recovery code.

------------------------------------------------------------------------

# 25. Security Work

Security should focus on actual attack surfaces.

Review:

-   authentication
-   refresh tokens
-   authorization
-   role enforcement
-   account claiming
-   sensitive information exposure
-   rate limiting
-   webhook verification
-   secret management
-   input validation
-   database access
-   error responses
-   auditability
-   administrative operations

Do not assume that authentication means authorization is complete.

Every sensitive action should answer:

> Who is allowed to perform this action?

and:

> Against which Chama or resource?

------------------------------------------------------------------------

# 26. Observability

Keep the existing observability direction.

Structured logs, request IDs, metrics, health checks, and readiness
checks should remain.

Improve them where useful.

For financial operations, it should be possible to correlate:

``` text
API request
    ↓
business operation
    ↓
payment event
    ↓
financial event
    ↓
ledger transaction
```

without exposing secrets or sensitive credentials.

Do not log sensitive payment credentials, authentication secrets, or
unnecessary personal information.

------------------------------------------------------------------------

# 27. Documentation Rules for Future Development

Every significant new feature should update the relevant documentation.

At minimum, a major financial feature should have:

``` text
Business rules
Architecture decision
Database changes
API behavior
State transitions
Financial effects
Testing strategy
Operational considerations
```

Do not create documentation after the feature has already become
difficult to explain.

Document decisions while they are being made.

------------------------------------------------------------------------

# 28. Agent and AI Development Rules

AI coding agents may be used, but they must operate under strict
repository rules.

An agent must not:

-   invent business rules
-   rewrite architecture without approval
-   modify financial semantics casually
-   bypass the ledger
-   delete tests because they fail
-   mark tests as skipped merely to make CI green
-   introduce new dependencies without justification
-   create duplicate models for existing concepts
-   create parallel accounting systems
-   change API contracts without documenting the change
-   modify unrelated modules while implementing a feature
-   perform broad refactoring as part of a feature task

An agent should first inspect:

``` text
AGENTS.md
project status
business rules
architecture
database specification
relevant ADRs
tests
```

before changing a financial subsystem.

------------------------------------------------------------------------

# 29. Definition of Done for a Financial Feature

A financial feature is not complete merely because its endpoint works.

A feature should be considered complete only when:

1.  Business rules are defined.
2.  Domain states are defined.
3.  Database changes are migrated.
4.  Authorization is enforced.
5.  Financial effects are mapped to the ledger.
6.  Idempotency is addressed.
7.  Concurrency risks are addressed.
8.  Failure paths are handled.
9.  Tests cover normal behavior.
10. Tests cover important failure behavior.
11. Duplicate requests are tested where relevant.
12. Documentation is updated.
13. Audit requirements are defined.
14. Reporting implications are understood.
15. PostgreSQL integration behavior is verified where relevant.

------------------------------------------------------------------------

# 30. Recommended Development Order

The developer should work in this order.

## Step 1: Repository consistency

Bring the documentation and actual implementation into agreement.

Do not change business behavior during this step.

## Step 2: Deferred test inventory

Document every deferred test and determine which can be activated.

Do not delete deferred tests.

## Step 3: Financial domain decisions

Resolve the remaining business questions for registration fees, loans,
repayments, and payouts.

Do not code around unresolved decisions.

## Step 4: Registration fee accounting

Complete the financial lifecycle.

## Step 5: Loans

Implement the agreed lifecycle and accounting behavior.

## Step 6: Repayments

Implement allocation, settlement, idempotency, and accounting.

## Step 7: Payouts

Implement authorization, approval, settlement, failure handling, and
accounting.

## Step 8: Financial reporting

Build reports from authoritative financial data.

## Step 9: Business audit trail

Add meaningful audit events for sensitive operations.

## Step 10: Security hardening

Perform targeted security review against the completed workflows.

## Step 11: Integration testing

Increase PostgreSQL and payment integration coverage.

## Step 12: Performance measurement

Measure real bottlenecks before introducing scaling infrastructure.

------------------------------------------------------------------------

# 31. Things That Are Explicitly Not Required Now

Do not introduce these unless a concrete requirement appears:

-   Microservices
-   Kubernetes
-   Kafka
-   Distributed databases
-   GraphQL
-   Event sourcing as a replacement for the existing design
-   CQRS as a blanket architecture
-   Redis everywhere
-   Multiple payment providers without a real requirement
-   A complete frontend rewrite
-   A new ORM
-   A new web framework
-   A new programming language
-   A complete repository restructure

These technologies are not automatically bad.

They are simply not the immediate problem.

------------------------------------------------------------------------

# 32. What "Scale" Means for This Project

Scaling ChamaCore should initially mean:

``` text
More members
More Chamas
More financial transactions
More payment events
More concurrent requests
More reports
More historical data
```

while preserving financial correctness.

It does not mean adding more infrastructure for its own sake.

The first scaling bottleneck is likely to be data access, transaction
behavior, background work, reporting queries, or operational
reliability.

Measure the actual bottleneck.

Then solve that bottleneck.

------------------------------------------------------------------------

# 33. Final Engineering Principle

The project should evolve like this:

``` text
Existing working architecture
        ↓
Targeted hardening
        ↓
Complete financial domain
        ↓
Reliable testing
        ↓
Operational visibility
        ↓
Measured performance improvements
        ↓
Controlled scale
```

Not:

``` text
Existing project
        ↓
Rewrite
        ↓
Microservices
        ↓
More infrastructure
        ↓
More infrastructure
        ↓
Still missing business rules
```

The first path scales the product.

The second path scales complexity.

------------------------------------------------------------------------

# 34. Final Developer Instruction

Treat the existing ChamaCore codebase as an asset.

Do not assume old code is bad merely because it is old.

Do not assume new code is better merely because it is cleaner.

Before changing an existing subsystem, understand why it exists.

Before adding a new financial operation, understand how the ledger
represents it.

Before changing the database, understand the migration history.

Before changing an API, understand its consumers.

Before adding infrastructure, identify the measured problem it solves.

Before using an AI agent, provide it with the repository rules and
relevant domain documentation.

The objective of this phase is not to produce the most impressive
architecture diagram.

The objective is to produce a ChamaCore system whose financial behavior
can be explained, tested, audited, operated, and extended without losing
control of the system.

**Preserve. Harden. Complete. Measure. Then scale.**
