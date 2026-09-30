# Backend Gap Analysis and Improvement Plan

**Reviewed:** 2026-09-30  
**Scope:** ChamaCore backend (`app/`, migrations, tests, and current operational documentation)  
**Review type:** Static code and documentation review. No test suite, load test, production deployment, or live payment-provider transaction was run for this report.

## Purpose

This report records implementation and operational gaps that are visible in the current backend, with practical steps for improving them. Findings marked **Confirmed** are directly supported by the code paths cited. Items marked **Measure / validate** are risks to investigate; this review does not claim that production incidents or performance degradation have occurred.

## Summary

The backend has a sound foundation for a financial service: a modular monolith, a ledger posting path, immutable financial records and reversals, idempotency mechanisms, a provider-neutral payment layer, payment event storage, and a production runbook. The largest opportunities are around recovering reliably from interrupted payment callbacks, bounding list responses, keeping audit evidence aligned with configuration changes, and adding evidence-based capacity planning before scaling beyond the documented single-process deployment.

## Prioritized findings

### P1 — A committed webhook inbox event can prevent callback recovery

**Status: Confirmed code-path reliability gap.**

`PaymentWebhookService._store_event()` commits a new event in `RECEIVED` state before `_apply_callback()` updates the payment attempt/intent and settles a linked contribution. If the process stops after the event commit but before the state transition completes, a provider retry with the same event ID and payload is changed to `DEDUPLICATED` and returned. That duplicate path does not resume processing the original `RECEIVED` event. The event can therefore remain recorded while the payment state or ledger settlement is incomplete.

Relevant code: `app/services/payment_webhook.py` (`handle`, `_store_event`, `_apply_callback`); `app/services/settlement.py`.

**Suggested improvement:** Make callback processing recoverable. Prefer a durable inbox state machine such as `RECEIVED → PROCESSING → PROCESSED`, with retryable failures and a dead-letter/reconciliation state. Ensure the financial state transition, linked ledger settlement, and processed marker share a database transaction where feasible. For external side effects, use an outbox or explicit idempotent workflow rather than holding a database transaction across a network call. A repeated event should be able to resume an unfinished event safely. Add a periodic job or operator command to find stale `RECEIVED`/`PROCESSING` events and retry or reconcile them.

**Acceptance evidence to add:** Tests simulating failure after inbox insert, before settlement, and during commit; repeated and out-of-order callbacks; duplicate IDs with matching and mismatching payload hashes; verify one and only one ledger posting after replay.

### P1 — Payment-connection audit records can diverge from committed changes

**Status: Confirmed for payment-connection service paths.**

`app/services/payment_connection.py` commits configuration changes and then calls `AuditService.record_commit()`, which records and commits the audit event in a separate transaction. If audit persistence fails after the first commit, the connection change can succeed without its audit record. The operation may also return an error even though the configuration change already committed, which can confuse clients retrying the request.

Relevant code: `app/services/payment_connection.py`; `app/services/audit.py` (`record` and `record_commit`).

**Suggested improvement:** For configuration operations, add the audit row in the same transaction as the change and commit once. Keep separately committed audit events only for actions that intentionally have no corresponding business transaction (for example, failed authentication attempts). Add a failure-injection test proving that a failed audit insert rolls back the configuration change, and a test proving a successful change always has its expected audit event.

### P1 — Concurrent financial decisions need explicit invariant review

**Status: Measure / validate; not established as a defect by this static review.**

Loan approvals, payouts, contribution settlement, and balance/cap checks must remain correct when two requests target the same Chama or member concurrently. A check-then-write flow can admit overspending if independent transactions both observe the same available balance before either posts. The ledger protects financial history, but it does not by itself prove that every business-level cap check is serialized.

**Suggested improvement:** Map the invariants for loan exposure, member payout limits, and available cash to their service transactions. For each invariant, document the locking/serialization mechanism (for example, locking a stable account or Chama row, a database constraint, or serializable retry). Add concurrent integration tests against PostgreSQL that race approvals and payouts and assert the invariant and balanced ledger remain intact. Avoid relying on SQLite concurrency tests for this proof.

### P2 — Several domain collection queries are unbounded

**Status: Confirmed in repository query implementations.**

The Chama-wide repositories for contributions, memberships, loans (including their repayments), payment connections, payment intents, and payouts return every matching row without a page limit. As a group grows, response time and memory use can grow with its full history. Audit has a default limit of 200, and ledger transaction/entry repositories already provide keyset pagination that can guide a consistent API pattern.

Relevant code: `app/repositories/contribution.py`, `membership.py`, `loan.py`, `payment.py`, `payout.py`, `audit.py`, and `ledger.py`.

**Suggested improvement:** Introduce bounded, stable pagination for collection APIs. Prefer keyset cursors using a deterministic ordering plus a unique tie-breaker for growing financial histories; use bounded page/offset only where the collection is small and stable. Set a maximum page size, return pagination metadata, and ensure frontend clients can request subsequent pages. Avoid eagerly loading all repayments for every loan in a list response; provide a loan detail endpoint or separately paged repayments.

### P2 — Current deployment model constrains horizontal scaling

**Status: Confirmed and already documented operational constraint.**

Rate-limit counters and the metrics registry are in process memory. The production runbook correctly specifies one Uvicorn process behind a load balancer and warns that multiple workers/processes split metrics and weaken rate limits. This is a capacity constraint rather than an unimplemented bug under the stated deployment model.

Relevant code/docs: `app/core/ratelimit.py`, `app/core/metrics.py`, `docs/12_PRODUCTION_RUNBOOK.md`.

**Suggested improvement:** Keep the single-process deployment until measured load requires more capacity. Before adding workers or replicas, move rate-limit state to a shared store or enforce appropriate limits at a trusted edge, and aggregate metrics centrally. Verify client identity handling at the proxy boundary so IP-based limits cannot be spoofed through untrusted forwarding headers. Document the deployment topology and safe worker count in release operations.

### P2 — Payment operations need recovery-focused visibility

**Status: Improvement opportunity; operational coverage should be checked against the deployed monitoring stack.**

The code stores payment events and provider transactions, which provides useful reconciliation data. The runbook describes metrics and basic service operations, but payment-specific signals are needed to spot a growing callback backlog, repeated provider failures, stuck intents, and mismatches before users report missing payments.

**Suggested improvement:** Add dashboards/alerts for callback counts by outcome, stale received/processing events, time from callback receipt to settlement, intents stuck in processing, provider initiation/validation error rates, duplicate/disagreement/unprocessable event rates, and reconciliation age. Use bounded-cardinality labels (provider, environment, outcome); do not label metrics with user IDs, phone numbers, raw callback bodies, transaction IDs, or secrets. Define an operator reconciliation procedure that can find provider-success/local-unsettled cases and resolve them through idempotent service paths.

### P2 — Performance characteristics are not yet evidenced by a reproducible workload

**Status: Measure / validate.**

This review did not run benchmarks or inspect production traces, so it cannot conclude that the service currently has a performance incident. Unbounded list queries and history-derived financial views are likely areas to measure as tenant data grows. Ledger balances are deliberately derived from posted entries, preserving correctness, but query cost should be measured with realistic ledger sizes.

**Suggested improvement:** Create a repeatable PostgreSQL benchmark with representative small, median, and large Chamas. Record throughput and p50/p95/p99 latency for login, list/detail APIs, contribution posting, loan repayment, payout, payment initiation, webhook handling, and ledger views. Capture query counts, rows scanned, lock waits, connection-pool saturation, and `EXPLAIN (ANALYZE, BUFFERS)` for slow queries. Use those results to choose indexes and pagination strategy; do not add denormalized balance caches without a reconciliation and correctness design.

### P2 — Payment edge cases need a documented end-to-end acceptance matrix

**Status: Recommendation.**

Payment integrations span provider initiation, asynchronous callback parsing, state transitions, and ledger settlement. Unit tests for each component are useful, but a compact acceptance matrix makes the cross-component financial outcomes explicit and protects against regressions when adding providers.

**Suggested improvement:** Maintain provider-neutral integration cases for: timeout after provider acceptance; callback before initiation response is persisted; callback replay; duplicate event ID with changed payload; out-of-order pending/failure/success callbacks; amount or currency mismatch; callback for unknown attempt; provider success after local timeout; terminal-state replay; successful payment with contribution settlement; and manual reconciliation after lost callback. Assert both payment state and exact ledger effects for every case.

## Suggested implementation sequence

1. **Payment recovery:** Add stale inbox detection and safe replay; make event processing and settlement atomic/idempotent; cover crash/retry boundaries.
2. **Audit alignment:** Put payment-connection change and audit insert in one transaction; test rollback behaviour.
3. **Financial concurrency:** Document critical invariants and prove them using PostgreSQL race tests and transaction-level locking/constraints.
4. **Bounded APIs:** Add stable pagination to unbounded list endpoints and avoid loading full related histories.
5. **Operational readiness:** Add payment-focused metrics, alerts, and a reconciliation procedure; use shared rate limits/metrics before horizontal scale-out.
6. **Performance baselines:** Benchmark representative data and workloads, then tune indexes and queries based on measured evidence.

## Scope and limitations

This is a code-informed improvement plan, not a security audit or production incident diagnosis. The callback and audit findings describe reachable failure windows in the inspected code paths; their occurrence rate depends on runtime failures. Concurrency risks and performance impact require targeted PostgreSQL tests and measurements. No source code or runtime configuration was changed as part of this report.
