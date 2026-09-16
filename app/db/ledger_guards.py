"""Database guard triggers for the immutable V2 ledger.

These objects are created both by the V2 hardening migration (the production
schema) and by the test harness after ``create_all``, so every test target
exercises the same database-level protections:

- UPDATE and DELETE on ``ledger_transactions`` and ``ledger_entries`` are
  rejected (ADR-011 append-only).
- On PostgreSQL, the balanced-transaction invariant is enforced by a deferred
  constraint trigger (ADR-012). SQLite cannot defer constraint checks, so the
  posting service remains the balancing authority there; the limitation is
  documented in ``docs/10_V2_FINANCIAL_CORE.md``.

``create_ledger_guards`` is idempotent: triggers are dropped before being
created and functions use ``CREATE OR REPLACE``. This lets the migration and
the test fixture both run it against the same database without duplicate-
trigger failures, while never weakening the installed protections.
"""

from sqlalchemy import Connection, text

SQLITE_DROP_TRIGGERS = """
DROP TRIGGER IF EXISTS "trg_ledger_transactions_no_update";

DROP TRIGGER IF EXISTS "trg_ledger_transactions_no_delete";

DROP TRIGGER IF EXISTS "trg_ledger_entries_no_update";

DROP TRIGGER IF EXISTS "trg_ledger_entries_no_delete";
"""

SQLITE_IMMUTABLE_TRIGGERS = """
CREATE TRIGGER trg_ledger_transactions_no_update BEFORE UPDATE ON ledger_transactions
BEGIN
    SELECT RAISE(ABORT, 'ledger transactions are immutable');
END;

CREATE TRIGGER trg_ledger_transactions_no_delete BEFORE DELETE ON ledger_transactions
BEGIN
    SELECT RAISE(ABORT, 'ledger transactions are immutable');
END;

CREATE TRIGGER trg_ledger_entries_no_update BEFORE UPDATE ON ledger_entries
BEGIN
    SELECT RAISE(ABORT, 'ledger entries are immutable');
END;

CREATE TRIGGER trg_ledger_entries_no_delete BEFORE DELETE ON ledger_entries
BEGIN
    SELECT RAISE(ABORT, 'ledger entries are immutable');
END;
"""

POSTGRES_DROP_TRIGGERS = """
DROP TRIGGER IF EXISTS trg_ledger_transactions_no_update ON ledger_transactions;

DROP TRIGGER IF EXISTS trg_ledger_transactions_no_delete ON ledger_transactions;

DROP TRIGGER IF EXISTS trg_ledger_entries_no_update ON ledger_entries;

DROP TRIGGER IF EXISTS trg_ledger_entries_no_delete ON ledger_entries;

DROP TRIGGER IF EXISTS trg_chama_core_ledger_transaction_balanced ON ledger_transactions;

DROP TRIGGER IF EXISTS trg_chama_core_ledger_entries_balanced ON ledger_entries;
"""

POSTGRES_IMMUTABLE_TRIGGERS = """
CREATE OR REPLACE FUNCTION chama_core_block_ledger_transactions_write()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'ledger transactions are immutable';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ledger_transactions_no_update
BEFORE UPDATE ON ledger_transactions
FOR EACH ROW EXECUTE FUNCTION chama_core_block_ledger_transactions_write();

CREATE TRIGGER trg_ledger_transactions_no_delete
BEFORE DELETE ON ledger_transactions
FOR EACH ROW EXECUTE FUNCTION chama_core_block_ledger_transactions_write();

CREATE OR REPLACE FUNCTION chama_core_block_ledger_entries_write()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'ledger entries are immutable';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ledger_entries_no_update
BEFORE UPDATE ON ledger_entries
FOR EACH ROW EXECUTE FUNCTION chama_core_block_ledger_entries_write();

CREATE TRIGGER trg_ledger_entries_no_delete
BEFORE DELETE ON ledger_entries
FOR EACH ROW EXECUTE FUNCTION chama_core_block_ledger_entries_write();
"""

POSTGRES_BALANCE_TRIGGERS = """
CREATE OR REPLACE FUNCTION chama_core_validate_ledger_transaction()
RETURNS trigger AS $$
DECLARE
    entry_count integer;
    total_debits numeric(18, 2);
    total_credits numeric(18, 2);
BEGIN
    SELECT COUNT(*), COALESCE(SUM(debit), 0), COALESCE(SUM(credit), 0)
      INTO entry_count, total_debits, total_credits
      FROM ledger_entries
     WHERE transaction_id = NEW.id;
    IF entry_count < 2 THEN
        RAISE EXCEPTION 'ledger transaction % must have at least two entries', NEW.id;
    END IF;
    IF total_debits <> total_credits THEN
        RAISE EXCEPTION 'ledger transaction % is unbalanced', NEW.id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER trg_chama_core_ledger_transaction_balanced
AFTER INSERT OR UPDATE ON ledger_transactions
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION chama_core_validate_ledger_transaction();

CREATE OR REPLACE FUNCTION chama_core_validate_ledger_entry_parent()
RETURNS trigger AS $$
DECLARE
    parent_id uuid;
    entry_count integer;
    total_debits numeric(18, 2);
    total_credits numeric(18, 2);
BEGIN
    parent_id := CASE WHEN TG_OP = 'DELETE' THEN OLD.transaction_id ELSE NEW.transaction_id END;
    SELECT COUNT(*), COALESCE(SUM(debit), 0), COALESCE(SUM(credit), 0)
      INTO entry_count, total_debits, total_credits
      FROM ledger_entries
     WHERE transaction_id = parent_id;
    IF entry_count < 2 THEN
        RAISE EXCEPTION 'ledger transaction % must have at least two entries', parent_id;
    END IF;
    IF total_debits <> total_credits THEN
        RAISE EXCEPTION 'ledger transaction % is unbalanced', parent_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER trg_chama_core_ledger_entries_balanced
AFTER INSERT OR UPDATE OR DELETE ON ledger_entries
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION chama_core_validate_ledger_entry_parent();
"""


def _execute_block(connection: Connection, sql: str) -> None:
    """Execute a SQL block split on blank lines, ignoring empty chunks."""
    for statement in sql.split("\n\n"):
        stripped = statement.strip()
        if stripped:
            connection.execute(text(stripped))


def create_ledger_guards(connection: Connection) -> None:
    """Create the ledger guard triggers for the current database dialect.

    This is idempotent: existing triggers and functions are dropped or
    replaced before creation, so running it twice against the same
    database never fails with duplicate-trigger errors.
    """
    dialect = connection.dialect.name
    if dialect == "sqlite":
        _execute_block(connection, SQLITE_DROP_TRIGGERS)
        _execute_block(connection, SQLITE_IMMUTABLE_TRIGGERS)
    elif dialect == "postgresql":
        _execute_block(connection, POSTGRES_DROP_TRIGGERS)
        _execute_block(connection, POSTGRES_IMMUTABLE_TRIGGERS)
        _execute_block(connection, POSTGRES_BALANCE_TRIGGERS)
    else:
        raise ValueError(f"Ledger guard triggers are not defined for dialect {dialect!r}")
