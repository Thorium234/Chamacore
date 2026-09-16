# ChamaCore V2 Ledger Review

## Review metadata

- Repository: `https://github.com/Thorium234/Chamacore`
- Branch: `main`
- Commit reviewed: `bbcc85c0965a78209ebe6aea4f9f28b1b90570b3`
- Commit message: `Add V2 financial ledger foundation with financial transaction history`
- Review date: 2026-09-16

## Executive verdict

The V2 ledger foundation is a good first increment and the repository is
passing its current automated checks:

```text
SQLite:       81 passed
PostgreSQL:   80 passed, 1 deselected
Concurrency:  1 passed
SQLite migration: passed
PostgreSQL migration: passed
Alembic check: no new upgrade operations
```

The implementation correctly keeps contribution posting, loans, repayments,
and payouts blocked while the associated business decisions remain open.
That no-guessing behavior is correct.

However, the ledger is not yet safe to call a fully enforced financial source
of truth. The main weaknesses are that some invariants exist only in the
service layer, idempotency can silently accept conflicting retries, and the
database does not fully enforce Chama ownership or immutability. These should
be fixed before connecting contributions or adding loans and payouts.

## What is implemented correctly

- Chama-scoped ledger accounts
- Double-entry posting service
- Debit/credit side validation
- Decimal quantization intent using `NUMERIC(18, 2)`
- Source-reference idempotency
- Compensating reversal service
- Active-membership authorization for ledger reads and posting
- Chama-scoped history endpoint
- Fresh V1 and V2 migrations
- SQLite and PostgreSQL test targets
- Open business decisions recorded instead of guessed

The 15 V2 tests cover the main happy paths, invalid posting shapes,
idempotency, reversals, authorization, and Chama scoping.

## Findings

### V2-001 — Quantization happens after validation

**Priority: P1 — fix before connecting any business event**

`app/services/ledger.py` validates the raw `Decimal` values in
`_validate_lines()` and only quantizes them while constructing database rows.
This contradicts ADR-013, which requires quantization before side and balance
validation.

For example, the current validator accepts:

```text
debit:  0.004
credit: 0.004
```

Both values then become `0.00`. The database check rejects the resulting rows,
but the service has already accepted a logically invalid posting and exposes a
low-level database error instead of a domain error.

The opposite problem also exists: values that balance after two-decimal
rounding can be rejected because the raw values do not balance.

**Fix:**

1. Quantize every amount first using `ROUND_HALF_UP`.
2. Reject non-finite values.
3. Reject any quantized amount that is zero or negative for its selected side.
4. Validate exactly one positive side per line.
5. Compare the quantized debit and credit totals.
6. Persist the already-normalized values.

**Tests to add:**

- `0.004` values are rejected as zero after quantization.
- `1.004` debit and `1.003` credit are treated according to the approved
  rounding rule.
- More than two decimal places never reaches the database.
- NaN and infinity are rejected with a domain error.

### V2-002 — Idempotent retries can silently accept conflicting payloads

**Priority: P1 — fix before external event retries**

`LedgerService.post_transaction()` returns the existing transaction as soon as
`(source_type, source_id)` exists. It does not compare the existing Chama,
description, reversal relationship, or normalized ledger lines with the retry.

That means a caller can retry the same source with different amounts or
different accounts and receive a successful response for the original
transaction. This hides a producer bug and makes financial reconciliation
harder.

There is also an inconsistent cross-Chama case:

- The first idempotency lookup returns `None` from
  `get_by_id_in_chama()` when the source exists in another Chama.
- The `IntegrityError` retry path returns the globally found transaction
  without applying the Chama filter.

**Fix:**

1. Treat a source reference as an immutable event identity.
2. When it already exists, compare the requested normalized payload with the
   stored transaction.
3. Return the existing transaction only when the payload matches.
4. Raise a domain `ConflictError` when the payload or Chama differs.
5. Never return a transaction belonging to another Chama.
6. Add a concurrency test for two callers posting the same source with
   conflicting payloads.

### V2-003 — Ledger entry ownership is not enforced by the database

**Priority: P1 — fix before trusting direct database access**

`ledger_entries` stores `transaction_id` and `account_id`, but it does not
store or constrain the Chama relationship between them. The database can
therefore accept:

```text
transaction from Chama A
account from Chama B
```

The service prevents this through `get_in_chama()`, but the migration does not
provide a database backstop. A future repository, maintenance script, direct
SQL client, or bug in another service could corrupt the ledger.

The same concern applies to `reverses_transaction_id`: the schema does not
enforce that the reversed transaction belongs to the same Chama.

**Fix options:**

- Add Chama ownership columns and composite foreign keys for transaction,
  account, and reversal relationships; or
- Use database triggers that reject cross-Chama ledger relationships.

The chosen option must work in PostgreSQL and have an equivalent SQLite test
for development.

**Tests to add:**

- Direct database insertion of a cross-Chama entry fails.
- Direct database insertion of a cross-Chama reversal fails.
- Service and database both reject cross-Chama references.

### V2-004 — Immutability is service-level, not actually enforced

**Priority: P1 — fix before production financial use**

ADR-011 says ledger transactions and entries are append-only. The current
implementation relies on the absence of public update/delete endpoints and the
absence of repository update/delete methods.

That is not a complete immutability guarantee:

- `TimestampMixin` gives ledger rows an `updated_at` column with
  `onupdate=func.now()`.
- `LedgerTransaction.entries` uses `cascade="all, delete-orphan"`.
- An ORM caller can update a ledger row or delete a transaction and its entries.
- A direct database client can update or delete rows unless database rules
  prevent it.

The `RESTRICT` foreign keys do not fully solve this because SQLAlchemy can
delete the child entries first through the relationship cascade.

**Fix:**

1. Remove mutable `updated_at` behavior from immutable ledger tables.
2. Add database protections against UPDATE and DELETE for ledger transactions
   and entries.
3. Use compensating transactions for every correction.
4. Add tests that attempt ORM update, ORM delete, and direct SQL update/delete.
5. Keep the service and repository APIs append-only.

PostgreSQL triggers are the strongest production control. SQLite triggers
should be added for development parity, or the limitation must be explicit.

### V2-005 — No database-level balanced-transaction invariant

**Priority: P2 — improve before production**

The service checks that total debits equal total credits, but the database only
checks each entry's individual side. A direct insert can create:

- a transaction with no entries,
- an unbalanced transaction,
- a transaction with only debits,
- a transaction with only credits.

Cross-row balance checks are not expressible as a normal `CHECK` constraint.
The current service is the intended write path, but the ledger is described as
the financial source of truth and should have a stronger boundary.

**Fix:**

- Keep service validation.
- Add a PostgreSQL deferred constraint trigger or a controlled database
  posting function that validates the complete transaction at commit.
- Add equivalent integration coverage.
- Document the exact SQLite limitation if a portable implementation is not
  possible.

### V2-006 — Reversal metadata is not fully validated

**Priority: P1 — fix before business reversal flows**

`reverse_transaction()` applies the intended rules, but
`post_transaction()` accepts `reverses_transaction_id` directly without
verifying that:

- the referenced transaction exists,
- it belongs to the same Chama,
- it is not the transaction being created,
- it has not already been reversed,
- the source type is the approved reversal source type.

The current tests exercise only the higher-level reversal method. A future
business posting integration could call the lower-level method incorrectly.

**Fix:**

- Move reversal creation behind a dedicated validated method, or
- validate all reversal metadata inside `post_transaction()`.
- Add database uniqueness for one reversal per original transaction, preferably
  as a partial unique index where `reverses_transaction_id IS NOT NULL`.

### V2-007 — Ledger account types are not fully constrained at the database layer

**Priority: P2**

The application uses `LedgerAccountType`, but the migration creates a
non-native string enum without an explicit database check constraint. A direct
database write may therefore insert an unsupported account type.

**Fix:**

- Add a database check constraint for the five approved account types, or use
  a PostgreSQL enum with an explicit SQLite-compatible equivalent.
- Add a migration and direct constraint test.
- Add validation for empty/whitespace account codes and names.

### V2-008 — Ledger history has no pagination or bounded query

**Priority: P2 — fix before real ledger volume**

`GET /api/v1/chamas/{chama_id}/ledger` loads and returns the complete history.
This will grow without bound and can create slow responses or memory pressure.

**Fix:**

- Add limit and cursor pagination.
- Order by `(created_at, id)` consistently.
- Add optional date/source filters only after documenting the API contract.
- Return pagination metadata.
- Add a query/index test for large history.

### V2-009 — Negative-path tests are too broad

**Priority: P2 — improve test quality**

Many V2 tests use `pytest.raises(Exception)`. This can allow a test to pass for
the wrong reason, including a database error instead of the intended domain
error.

**Fix:**

- Assert `StateError`, `ConflictError`, and `PermissionDeniedError`
  specifically.
- Assert HTTP error payload codes for endpoint tests.
- Use `IntegrityError` only where a direct database constraint is the behavior
  under test.
- Add rollback assertions after failed service operations.

### V2-010 — Review report and verification metadata are stale

**Priority: P3**

`reports/02_v2_ledger_foundation.md` reports that PostgreSQL was not runnable
because Docker was unavailable. The current verification environment was able
to run PostgreSQL locally, and the repository is now at commit `bbcc85c`.

The report should be refreshed with the current commit and the actual
PostgreSQL result:

```text
80 passed, 1 deselected
1 concurrency test passed
```

This is documentation hygiene, not an application defect.

## Intentional blockers, not missed features

These are correctly not implemented yet:

- Default chart of accounts and account maintenance
- Contribution-to-ledger posting
- Registration-fee payment posting
- Loans and repayments
- Interest and service charges
- Repayment schedules and defaults
- Payouts and payout approval
- Payment providers and reconciliation

The open questions OQ-012 through OQ-020 correctly block these areas. The
agent should not invent those rules.

## Recommended fix order

### Phase 1 — ledger correctness

1. Fix quantization-before-validation.
2. Fix conflicting idempotency and cross-Chama source handling.
3. Validate reversal metadata.
4. Add direct constraint and rollback tests.

### Phase 2 — ledger protection

5. Enforce Chama ownership at the database boundary.
6. Enforce append-only behavior with database protections.
7. Decide whether balance validation uses a database trigger or a controlled
   posting function.
8. Add the account-type database constraint.

### Phase 3 — operational usability

9. Add paginated ledger history.
10. Strengthen test exception assertions.
11. Refresh the V2 report and CI verification evidence.

### Phase 4 — connect business events

Only after the above fixes and after resolving OQ-012/OQ-013:

1. Seed and maintain the approved Chama chart of accounts.
2. Connect confirmed contributions to one idempotent ledger posting.
3. Connect contribution reversal to a compensating ledger posting.
4. Add balances and financial reports from ledger entries.
5. Resolve loan and payout questions before implementing those workflows.

## Final recommendation

Do not begin loans, payouts, or payment integrations yet. The next coding
increment should harden the ledger boundary and make its invariants durable in
both the service and database layers. After that, resolve the chart-of-accounts
and contribution-posting questions and connect V1 contribution events to the
ledger.