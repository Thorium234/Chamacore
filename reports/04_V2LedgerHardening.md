# ChamaCore V2 Ledger Hardening Report

## Verification metadata

- Repository: `https://github.com/Thorium234/Chamacore`
- Branch: `main`
- Review report addressed: `reports/03_V2LedgerReviewReport.md`
- Hardening commit: see git log for the commit following this report
- Report date: 2026-09-16

## Verification environment

```text
SQLite:       109 passed (dev, Windows)
Concurrency:  2 passed (SQLite, dev)
Dev DB migration (sqlite:///./chamacore.db): passed
Alembic check after head migration: no new upgrade operations
compileall: clean
PostgreSQL:   CI jobs (test-postgres, concurrency-postgres)
```

PostgreSQL cannot be exercised locally (no Docker); native PostgreSQL
trigger/constraint paths are verified in CI only, as documented in
`docs/10_V2_FINANCIAL_CORE.md` and `ADR-015`.

## How each finding was resolved

### V2-001 — Quantization before validation — RESOLVED

`LedgerService.post_transaction` now calls `_normalize_lines()` first, which
quantizes every amount with `ROUND_HALF_UP` to two decimal places
(`CENT = Decimal("0.01")`), rejects bool/float/non-finite/invalid values,
and does so **before** `_validate_lines()` runs. The normalized values are
what gets validated, reconciled, and persisted.

Evidence:
- `app/services/ledger.py` — `_normalize_lines`, `_to_quantized`,
  `post_transaction` ordering.
- `tests/test_ledger.py`:
  - `test_post_quantizes_zero_amounts_then_rejects` — `0.004` pairs are
    rejected with a domain error, nothing persisted.
  - `test_post_round_half_up_reconciles_sub_cent_amounts` — `1.004`/`1.003`
    both store `1.00`.
  - `test_post_quantizes_half_up` — half-up always rounds up to `10.01`.
  - `test_post_stored_amounts_have_two_decimals` — `100.205` → `100.21`.
  - `test_post_rejects_non_finite_amounts` — NaN/Infinity → domain error.

### V2-002 — Conflicting idempotent retries rejected — RESOLVED

`_resolve_idempotent_retry()` now compares the stored transaction against the
normalized retry payload:

- Chama must match (never return a transaction from another Chama).
- Description must match.
- Reversal reference must match.
- Sorted ledger lines (account, debit, credit) must match.

Any mismatch raises `ConflictError`. The `IntegrityError` retry path also
goes through the same resolver, so a cross-Chama source can never leak a
foreign transaction.

Evidence:
- `app/services/ledger.py` — `_resolve_idempotent_retry`,
  `post_transaction` IntegrityError branch.
- `tests/test_ledger.py`:
  - `test_idempotent_retry_returns_same_transaction`
  - `test_idempotent_retry_with_different_amounts_conflicts`
  - `test_idempotent_retry_with_different_accounts_conflicts`
  - `test_idempotent_retry_with_different_description_conflicts`
  - `test_idempotent_retry_for_source_in_another_chama_conflicts`
- `tests/test_concurrency.py` — `TestLedgerSourceConcurrency` posts the same
  source from two threads with different amounts; exactly one wins and the
  other records a conflict.

### V2-003 — Chama ownership enforced by the database — RESOLVED

`ledger_entries` gains a denormalized `chama_id`. Composite foreign keys
make cross-Chama references structurally impossible:

- `fk_ledger_entries_transaction_chama`:
  `(chama_id, transaction_id) → ledger_transactions (chama_id, id)`
- `fk_ledger_entries_account_chama`:
  `(chama_id, account_id) → ledger_accounts (chama_id, id)`
- `fk_ledger_transactions_reversal_chama`:
  `(chama_id, reverses_transaction_id) → ledger_transactions (chama_id, id)`

Both `ledger_transactions` and `ledger_accounts` have `UNIQUE (chama_id, id)`
as composite targets. `create_transaction` sets `chama_id` on every entry.

Evidence:
- `app/models/ledger_transaction.py`, `app/models/ledger_entry.py`,
  `app/models/ledger_account.py`.
- `tests/test_ledger_db_enforcement.py`:
  - `test_db_rejects_cross_chama_ledger_entry`
  - `test_db_rejects_cross_chama_reversal`
  - `test_service_populates_chama_id_on_entries`

### V2-004 — Ledger tables truly append-only — RESOLVED

- `updated_at` removed from `ledger_transactions` and `ledger_entries`
  (already absent from `ledger_entries` model prior; transactions gained it
  via `TimestampMixin`). `ledger_accounts` keeps `updated_at`.
- Guard triggers installed on SQLite and PostgreSQL:
  `trg_ledger_transactions_no_update`, `trg_ledger_transactions_no_delete`,
  `trg_ledger_entries_no_update`, `trg_ledger_entries_no_delete`.
- The `LedgerTransaction.entries` `delete-orphan` cascade is removed; the
  relationship is now `viewonly=True` and the repository writes entries with
  explicit `chama_id`.

Evidence:
- `app/db/ledger_guards.py` — shared SQLite/PostgreSQL trigger DDL.
- `app/models/ledger_transaction.py`, `app/models/ledger_entry.py`.
- `tests/test_ledger_db_enforcement.py`:
  - `test_db_blocks_update_of_ledger_transaction`
  - `test_db_blocks_delete_of_ledger_transaction`
  - `test_db_blocks_update_of_ledger_entry`
  - `test_db_blocks_delete_of_ledger_entry`
- Dev DB schema inspected after `alembic upgrade head`: all four triggers
  present, `updated_at` gone, `viewonly` relationship confirmed by warning
  removal.

### V2-005 — Balanced-transaction invariant — PARTIAL (documented limitation)

PostgreSQL gets deferred constraint triggers:

- `trg_chama_core_ledger_transaction_balanced` — the posting transaction
  must reference a balanced transaction (≥2 entries, equal debit/credit
  sums) at commit.
- `trg_chama_core_ledger_entries_balanced` — every entry's parent
  transaction must be balanced; re-checked on entry insert/update/delete.

SQLite cannot defer constraint triggers, so the balanced invariant remains
application-enforced there. This limitation is explicit in:
- `app/db/ledger_guards.py` (SQLite branch installs only the four
  immutability triggers),
- `docs/decisions/ADR-015-ledger-hardening.md` (V2-005 section),
- this report.

### V2-006 — Reversal metadata validated + one-reversal DB index — RESOLVED

`post_transaction` now enforces reversal metadata before the idempotency
lookup:

- a reversal (`source_type == REVERSAL_SOURCE_TYPE`) must reference the
  transaction it reverses;
- a non-reversal may not carry `reverses_transaction_id`;
- `_validate_reversal_reference` checks the target exists in the same Chama,
  is not itself a reversal, and has no existing reversal.

The DB partial unique index `uq_ledger_transactions_reversal` on
`reverses_transaction_id WHERE reverses_transaction_id IS NOT NULL`
permits at most one reversal per original transaction.

Evidence:
- `app/services/ledger.py` — reversal branch, `_validate_reversal_reference`.
- `app/models/ledger_transaction.py` — partial unique index.
- `tests/test_ledger.py`:
  - `test_post_reversal_reference_missing_rejected`
  - `test_post_reversal_reference_to_other_chama_rejected`
  - `test_post_reversal_requires_source_type`
  - `test_post_reversal_source_requires_reference`
  - `test_post_direct_reversal_twice_conflicts`
  - `test_double_reversal_rejected`
  - `test_reversal_of_reversal_rejected`
  - `test_reversal_creates_compensating_transaction`
- `tests/test_ledger_db_enforcement.py`:
  - `test_db_blocks_second_reversal_of_same_transaction`

### V2-007 — Account type and blank code/name constrained — RESOLVED

- `ck_ledger_accounts_type`:
  `account_type IN ('ASSET','LIABILITY','EQUITY','REVENUE','EXPENSE')`.
  Added because the non-native `Enum` emits no CHECK on SQLite or
  PostgreSQL.
- `ck_ledger_accounts_non_blank`:
  `length(trim(code)) > 0 AND length(trim(name)) > 0`.

Evidence:
- `app/models/ledger_account.py`.
- `tests/test_ledger_db_enforcement.py`:
  - `test_db_rejects_unsupported_account_type`
  - `test_db_rejects_blank_account_code`
  - `test_db_rejects_blank_account_name`

### V2-008 — Cursor pagination for ledger history — RESOLVED

`GET /api/v1/chamas/{chama_id}/ledger` now:

- accepts `limit` (1–100, default 25) and an opaque `cursor`;
- performs keyset pagination ordered by `(created_at DESC, id DESC)`, fetches
  `limit + 1` rows to detect `has_more`;
- returns `LedgerHistoryOut { items, next_cursor, has_more }`;
- returns 422 for a malformed cursor;
- normalizes timestamp comparison for SQLite (`func.strftime` to seconds) so
  the cursor filter matches the stored `CURRENT_TIMESTAMP` format.

Evidence:
- `app/api/v1/ledger.py`, `app/repositories/ledger.py`,
  `app/schemas/ledger.py`.
- `tests/test_ledger.py`:
  - `test_ledger_endpoint_paginates`
  - `test_get_ledger_endpoint_returns_history`
  - `test_ledger_endpoint_rejects_malformed_cursor`

### V2-009 — Negative-path tests tightened — RESOLVED

The `pytest.raises(Exception)` calls were replaced with specific exceptions:
`StateError`, `ConflictError`, `PermissionDeniedError`, and `IntegrityError`
only where a database constraint is the behavior under test. Half-up and
zero-after-quantization cases assert rollback (no rows persisted).

Evidence:
- `tests/test_ledger.py` — all negative-path tests use the specific
  exception and assert non-persistence where applicable.
- `tests/test_ledger_db_enforcement.py` — direct database constraint tests
  assert `IntegrityError`.

### V2-010 — Report and verification metadata refreshed — RESOLVED

This report (`reports/04_V2LedgerHardening.md`) records the current commit,
the local SQLite results, the CI PostgreSQL jobs, and the ADR-015 decision
that codifies the hardening. The stale `reports/02_v2_ledger_foundation.md`
reference is superseded here.

## CI matrix

| Job | Command | Runs |
| --- | --- | --- |
| `test-sqlite` | `pytest -q` | all tests |
| `test-postgres` | `pytest -q -m "not concurrency"` | PG constraints/triggers |
| `concurrency-postgres` | concurrency-marked tests | PG uniqueness/triggers |

Native PostgreSQL verification (composite FKs, guard + balancing triggers,
partial unique index, migration) is performed by the CI `test-postgres` and
`concurrency-postgres` jobs.

## Skipped work (correctly blocked)

The findings that are business rules, not defects, remain unguessed:

- Default chart of accounts (OQ-012)
- Contribution-to-ledger posting (OQ-012/OQ-013)
- Registration-fee payment posting (OQ-014)
- Loans, repayments, payouts (OQ-015..OQ-020)

## Sign-off

All P1/P2 ledger-correctness and ledger-protection findings from
`reports/03_V2LedgerReviewReport.md` are resolved. Phase 4 (connect business
events to the ledger) remains blocked pending OQ-012/OQ-013, exactly as the
review recommended.