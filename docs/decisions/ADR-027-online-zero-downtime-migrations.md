# ADR-027: Online Zero-Downtime Database Migrations

## Status
Accepted

## Context
As ChamaCore scales and serves live financial groups across Kenya, scheduled maintenance windows and database downtime must be eliminated. Naive schema migrations (such as adding non-null columns without defaults, renaming columns in place, or holding exclusive locks during index builds) cause application errors and transaction timeouts.

## Decision
1. **Expand $\to$ Migrate/Backfill $\to$ Contract:** All non-trivial schema changes must be broken into backward-compatible stages across distinct releases.
2. **Lock Timeouts in PostgreSQL:** Production migrations must set strict `lock_timeout` (e.g. 2–3s) and `statement_timeout` to fail fast rather than accumulating queued blocked transactions.
3. **Mandatory Rollback Plans:** No migration may be executed in production without an explicitly completed Rollback Plan template tested against an anonymized staging snapshot.
4. **Restartable Backfills:** Data backfills must run in small, idempotent batches that can be interrupted and resumed safely without table locks.

## Consequences & Failure Modes
- Schema evolution requires more planning and multiple release cycles rather than instantaneous changes.
- Rollbacks are validated before any production DDL is applied.
