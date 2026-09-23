"""Database guard triggers for the append-only audit event log (ADR-023).

These objects are created both by the financial-domain migration (production
schema) and by the test harness after ``create_all``, so every test exercises
the same database-level protection: audit events can only be inserted, never
updated or deleted. Corrections are recorded as new events that reference the
corrected event; the history is never mutated in place.
"""

from sqlalchemy import Connection, text

SQLITE_DROP_TRIGGERS = """
DROP TRIGGER IF EXISTS "trg_audit_events_no_update";

DROP TRIGGER IF EXISTS "trg_audit_events_no_delete";
"""

SQLITE_IMMUTABLE_TRIGGERS = """
CREATE TRIGGER trg_audit_events_no_update BEFORE UPDATE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit events are immutable');
END;

CREATE TRIGGER trg_audit_events_no_delete BEFORE DELETE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit events are immutable');
END;
"""

POSTGRES_DROP_TRIGGERS = """
DROP TRIGGER IF EXISTS trg_audit_events_no_update ON audit_events;

DROP TRIGGER IF EXISTS trg_audit_events_no_delete ON audit_events;
"""

POSTGRES_IMMUTABLE_TRIGGERS = """
CREATE OR REPLACE FUNCTION chama_core_block_audit_events_write()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit events are immutable';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_events_no_update
BEFORE UPDATE ON audit_events
FOR EACH ROW EXECUTE FUNCTION chama_core_block_audit_events_write();

CREATE TRIGGER trg_audit_events_no_delete
BEFORE DELETE ON audit_events
FOR EACH ROW EXECUTE FUNCTION chama_core_block_audit_events_write();
"""


def _execute_block(connection: Connection, sql: str) -> None:
    for statement in sql.split("\n\n"):
        stripped = statement.strip()
        if stripped:
            connection.execute(text(stripped))


def create_audit_guards(connection: Connection) -> None:
    """Create the append-only audit triggers for the current database dialect.

    Idempotent: existing triggers and functions are dropped or replaced before
    creation, so running it twice against the same database never fails with
    duplicate-trigger errors.
    """
    dialect = connection.dialect.name
    if dialect == "sqlite":
        _execute_block(connection, SQLITE_DROP_TRIGGERS)
        _execute_block(connection, SQLITE_IMMUTABLE_TRIGGERS)
    elif dialect == "postgresql":
        _execute_block(connection, POSTGRES_DROP_TRIGGERS)
        _execute_block(connection, POSTGRES_IMMUTABLE_TRIGGERS)
    else:
        raise ValueError(f"Audit guard triggers are not defined for dialect {dialect!r}")