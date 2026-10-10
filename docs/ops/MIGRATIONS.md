# Online Zero-Downtime Database Migrations

**Audience:** Platform engineers, database operators, release managers  
**Applies to:** Alembic migrations for PostgreSQL (production) and SQLite (local dev)  
**Governing principle:** No full outage for schema changes. All migrations must follow the **Expand $\to$ Migrate $\to$ Contract** pattern.

---

## 1. Golden Rules for Online Migrations

Never execute any of the following operations in a single step on production tables:
- **Dropping a column or table** while running application instances might still read or write to it.
- **Renaming a column or table in-place** without dual-read/dual-write support.
- **Adding a `NOT NULL` column** without a default value or backfill strategy.
- **Adding or modifying Foreign Keys or Check Constraints** with long-held exclusive locks.
- **Adding large indexes** without `CONCURRENTLY` (PostgreSQL).

---

## 2. The Expand $\to$ Migrate/Backfill $\to$ Contract Pattern

When altering schema shapes, break changes into phased releases:

```
[Release N]           [Release N.1 / Background]    [Release N+1]          [Release N+2]
Expand Schema    -->  Backfill Data            -->  Switch Reads/Writes --> Contract Schema
Add new column        Populate new column           Application switches    Drop old column
or table (nullable)   in idempotent batches         to using new column     or deprecated table
```

### Phase 1: Expand
- Add the new column as `nullable=True` (or with a safe server-level default).
- Deploy application version that writes to both columns (or reads old with fallback).
- Keep foreign keys unconstrained or validate them asynchronously.

### Phase 2: Backfill
- Run a background script or restartable Alembic step to populate historical rows.
- Chunk updates (e.g. 1,000–5,000 rows at a time) to prevent table bloat and lock contention.
- Set short lock timeouts in PostgreSQL (`SET lock_timeout = '3s';`).

### Phase 3: Switch
- Deploy application code that reads and writes exclusively to the new column/shape.
- Verify through application metrics and logs that zero reads hit the legacy shape.

### Phase 4: Contract
- In a subsequent deployment window, drop the legacy column, index, or table.
- Mark columns `nullable=False` only after 100% of rows are backfilled.

---

## 3. PostgreSQL Lock Safety & Timeouts

In PostgreSQL, DDL locks the entire table (`ACCESS EXCLUSIVE`). Any queued queries behind it get blocked, causing connection pool exhaustion.

All production migration revisions must specify explicit statement and lock timeouts:

```python
# In alembic revision:
def upgrade():
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        conn.execute(sa.text("SET lock_timeout = '2s';"))
        conn.execute(sa.text("SET statement_timeout = '30s';"))
    
    # DDL operations here...
```

---

## 4. Staging Dry-Run Procedure

No database migration may run in production without passing the staging dry-run gate.

### Staging Verification Checklist:
1. **Database Snapshot:** Staging database must be restored from an anonymized production snapshot (similar size and distribution).
2. **Execution Order:**
   ```bash
   alembic upgrade head
   python -m app.db.verify_schema
   ```
3. **Smoke Tests:**
   - [ ] Run health check: `GET /health` and `GET /ready`
   - [ ] Authenticate user and rotate refresh token
   - [ ] Query Chama dashboard and ledger balance (`GET /api/v1/chamas/{id}/ledger/accounts`)
   - [ ] Execute test payment intent creation
   - [ ] Confirm idempotency triggers and composite foreign keys remain intact
4. **Approval Gate:** Record staging run duration, locks observed, and query timings in the release ticket before executing in production.

---

## 5. Rollback Plan Template

Every schema change requiring migration must have this template completed **prior** to production execution:

```text
=============================================================================
PRODUCTION MIGRATION ROLLBACK PLAN
=============================================================================
Migration ID:               <e.g. 7f3b8a1c9e2d>
Author / Operator:          <Name / Handle>
Staging Run Date:           <YYYY-MM-DD>
Staging Run Result:         [ PASS / FAIL ] (attach logs)
Target Release Window:      <YYYY-MM-DD HH:MM UTC>

Forward Steps:
1. alembic upgrade <target_revision>
2. python -m scripts.backfill_<feature> (if applicable)
3. Deploy application release vX.Y.Z

Rollback Steps (in order):
1. Revert application deployment to previous release vX.Y.(Z-1)
2. Verify application is stable on legacy code reading dual-write data
3. If necessary, execute: alembic downgrade -1
4. Verify schema state using: alembic current

Data That Cannot Be Restored (Non-reversible mutations):
- <Document any transformed or merged data that cannot be recovered via downgrade>

Communication & Freeze Window:
- Maintenance notice sent:  [ Yes / Not Required ]
- On-call Engineer:         <Name / Contact>
=============================================================================
```
