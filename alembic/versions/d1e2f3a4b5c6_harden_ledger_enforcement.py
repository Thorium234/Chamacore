"""harden ledger enforcement: ownership, immutability, balance, account types

Revision ID: d1e2f3a4b5c6
Revises: c7d8e9f0a1b2
Create Date: 2026-09-16 12:00:00.000000

Addresses the findings in reports/03_V2LedgerReviewReport.md:

- V2-003: Chama ownership of ledger entries and reversals enforced with
  composite foreign keys (ledger_entries gains a denormalized chama_id).
- V2-004: ledger tables become truly append-only — `updated_at` is removed
  and UPDATE/DELETE guard triggers are installed (SQLite and PostgreSQL).
- V2-005: PostgreSQL gets a deferred constraint trigger for the
  balanced-transaction invariant (SQLite limitation is documented).
- V2-006: one reversal per original transaction enforced with a partial
  unique index.
- V2-007: explicit account_type CHECK and non-blank code/name CHECKs.

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from app.db.ledger_guards import create_ledger_guards

revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SQLITE_ENTRIES_NEW = """
CREATE TABLE ledger_entries_new (
    chama_id CHAR(32) NOT NULL,
    transaction_id CHAR(32) NOT NULL,
    account_id CHAR(32) NOT NULL,
    debit NUMERIC(18, 2) NOT NULL,
    credit NUMERIC(18, 2) NOT NULL,
    id CHAR(32) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_ledger_entries_non_negative CHECK (debit >= 0 AND credit >= 0),
    CONSTRAINT ck_ledger_entries_single_side CHECK (
        (debit > 0 AND credit = 0) OR (debit = 0 AND credit > 0)
    ),
    CONSTRAINT fk_ledger_entries_transaction_chama
        FOREIGN KEY (chama_id, transaction_id)
        REFERENCES ledger_transactions (chama_id, id) ON DELETE RESTRICT,
    CONSTRAINT fk_ledger_entries_account_chama
        FOREIGN KEY (chama_id, account_id)
        REFERENCES ledger_accounts (chama_id, id) ON DELETE RESTRICT
)
"""

SQLITE_TRANSACTIONS_NEW = """
CREATE TABLE ledger_transactions_new (
    id CHAR(32) NOT NULL,
    chama_id CHAR(32) NOT NULL,
    source_type VARCHAR(64) NOT NULL,
    source_id CHAR(32) NOT NULL,
    description VARCHAR(255),
    posted_by_user_id CHAR(32) NOT NULL,
    reverses_transaction_id CHAR(32),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_ledger_transactions_source UNIQUE (source_type, source_id),
    CONSTRAINT uq_ledger_transactions_chama_id UNIQUE (chama_id, id),
    CONSTRAINT fk_ledger_transactions_reversal_chama
        FOREIGN KEY (chama_id, reverses_transaction_id)
        REFERENCES ledger_transactions (chama_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (chama_id) REFERENCES chamas (id) ON DELETE RESTRICT,
    FOREIGN KEY (posted_by_user_id) REFERENCES users (id) ON DELETE RESTRICT
)
"""

SQLITE_ACCOUNTS_NEW = """
CREATE TABLE ledger_accounts_new (
    id CHAR(32) NOT NULL,
    chama_id CHAR(32) NOT NULL,
    code VARCHAR(32) NOT NULL,
    name VARCHAR(120) NOT NULL,
    account_type VARCHAR(20) NOT NULL,
    description VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_ledger_accounts_chama_code UNIQUE (chama_id, code),
    CONSTRAINT uq_ledger_accounts_chama_id UNIQUE (chama_id, id),
    CONSTRAINT ck_ledger_accounts_type CHECK (
        account_type IN ('ASSET', 'LIABILITY', 'EQUITY', 'REVENUE', 'EXPENSE')
    ),
    CONSTRAINT ck_ledger_accounts_non_blank CHECK (
        length(trim(code)) > 0 AND length(trim(name)) > 0
    ),
    FOREIGN KEY (chama_id) REFERENCES chamas (id) ON DELETE RESTRICT
)
"""

COPIES = {
    "ledger_entries": """
        INSERT INTO ledger_entries_new
            (id, chama_id, transaction_id, account_id, debit, credit, created_at)
        SELECT
            e.id,
            t.chama_id,
            e.transaction_id,
            e.account_id,
            e.debit,
            e.credit,
            e.created_at
        FROM ledger_entries e
        JOIN ledger_transactions t ON t.id = e.transaction_id
    """,
    "ledger_transactions": """
        INSERT INTO ledger_transactions_new
            (id, chama_id, source_type, source_id, description,
             posted_by_user_id, reverses_transaction_id, created_at)
        SELECT
            id, chama_id, source_type, source_id, description,
            posted_by_user_id, reverses_transaction_id, created_at
        FROM ledger_transactions
    """,
    "ledger_accounts": """
        INSERT INTO ledger_accounts_new
            (id, chama_id, code, name, account_type, description,
             created_at, updated_at)
        SELECT
            id, chama_id, code, name, account_type, description,
            created_at, updated_at
        FROM ledger_accounts
    """,
}


def _recreate_sqlite_table(name: str) -> None:
    create_sql = {
        "ledger_entries": SQLITE_ENTRIES_NEW,
        "ledger_transactions": SQLITE_TRANSACTIONS_NEW,
        "ledger_accounts": SQLITE_ACCOUNTS_NEW,
    }[name]
    op.execute(sa.text(create_sql))
    op.execute(sa.text(COPIES[name]))
    op.execute(sa.text(f'DROP TABLE "{name}"'))
    op.execute(sa.text(f'ALTER TABLE "{name}_new" RENAME TO "{name}"'))


def _upgrade_sqlite() -> None:
    _recreate_sqlite_table("ledger_transactions")
    _recreate_sqlite_table("ledger_accounts")
    _recreate_sqlite_table("ledger_entries")
    op.execute(sa.text('CREATE INDEX "ix_ledger_transactions_chama_created" '
                       'ON ledger_transactions (chama_id, created_at)'))
    op.execute(sa.text(
        'CREATE UNIQUE INDEX "uq_ledger_transactions_reversal" '
        'ON ledger_transactions (reverses_transaction_id) '
        'WHERE reverses_transaction_id IS NOT NULL'
    ))
    create_ledger_guards(op.get_bind())


def _upgrade_postgresql() -> None:
    op.create_unique_constraint(
        "uq_ledger_accounts_chama_id", "ledger_accounts", ["chama_id", "id"]
    )
    op.create_check_constraint(
        "ck_ledger_accounts_type",
        "ledger_accounts",
        "account_type IN ('ASSET', 'LIABILITY', 'EQUITY', 'REVENUE', 'EXPENSE')",
    )
    op.create_check_constraint(
        "ck_ledger_accounts_non_blank",
        "ledger_accounts",
        "length(trim(code)) > 0 AND length(trim(name)) > 0",
    )

    op.create_unique_constraint(
        "uq_ledger_transactions_chama_id", "ledger_transactions", ["chama_id", "id"]
    )
    op.drop_constraint(
        "ledger_transactions_reverses_transaction_id_fkey",
        "ledger_transactions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_ledger_transactions_reversal_chama",
        "ledger_transactions",
        "ledger_transactions",
        ["chama_id", "reverses_transaction_id"],
        ["chama_id", "id"],
        ondelete="RESTRICT",
    )
    op.drop_column("ledger_transactions", "updated_at")
    op.create_index(
        "uq_ledger_transactions_reversal",
        "ledger_transactions",
        ["reverses_transaction_id"],
        unique=True,
        postgresql_where=sa.text("reverses_transaction_id IS NOT NULL"),
    )

    op.add_column("ledger_entries", sa.Column("chama_id", sa.Uuid(), nullable=True))
    op.execute(sa.text(
        "UPDATE ledger_entries e "
        "SET chama_id = (SELECT t.chama_id FROM ledger_transactions t WHERE t.id = e.transaction_id)"
    ))
    op.alter_column("ledger_entries", "chama_id", nullable=False)
    op.drop_constraint(
        "ledger_entries_account_id_fkey", "ledger_entries", type_="foreignkey"
    )
    op.drop_constraint(
        "ledger_entries_transaction_id_fkey", "ledger_entries", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_ledger_entries_account_chama",
        "ledger_entries",
        "ledger_accounts",
        ["chama_id", "account_id"],
        ["chama_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_ledger_entries_transaction_chama",
        "ledger_entries",
        "ledger_transactions",
        ["chama_id", "transaction_id"],
        ["chama_id", "id"],
        ondelete="RESTRICT",
    )
    op.drop_column("ledger_entries", "updated_at")

    create_ledger_guards(op.get_bind())


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        _upgrade_sqlite()
    else:
        _upgrade_postgresql()


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        _downgrade_sqlite()
    else:
        _downgrade_postgresql()


def _drop_guards_sqlite() -> None:
    for trigger in (
        "trg_ledger_transactions_no_update",
        "trg_ledger_transactions_no_delete",
        "trg_ledger_entries_no_update",
        "trg_ledger_entries_no_delete",
    ):
        op.execute(sa.text(f'DROP TRIGGER IF EXISTS "{trigger}"'))
    op.execute(sa.text('DROP INDEX IF EXISTS "uq_ledger_transactions_reversal"'))


SQLITE_ORIGINAL_ENTRIES = """
CREATE TABLE ledger_entries_new (
    transaction_id CHAR(32) NOT NULL,
    account_id CHAR(32) NOT NULL,
    debit NUMERIC(18, 2) NOT NULL,
    credit NUMERIC(18, 2) NOT NULL,
    id CHAR(32) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_ledger_entries_non_negative CHECK (debit >= 0 AND credit >= 0),
    CONSTRAINT ck_ledger_entries_single_side CHECK (
        (debit > 0 AND credit = 0) OR (debit = 0 AND credit > 0)
    ),
    FOREIGN KEY (transaction_id) REFERENCES ledger_transactions (id) ON DELETE RESTRICT,
    FOREIGN KEY (account_id) REFERENCES ledger_accounts (id) ON DELETE RESTRICT
)
"""

SQLITE_ORIGINAL_TRANSACTIONS = """
CREATE TABLE ledger_transactions_new (
    id CHAR(32) NOT NULL,
    chama_id CHAR(32) NOT NULL,
    source_type VARCHAR(64) NOT NULL,
    source_id CHAR(32) NOT NULL,
    description VARCHAR(255),
    posted_by_user_id CHAR(32) NOT NULL,
    reverses_transaction_id CHAR(32),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_ledger_transactions_source UNIQUE (source_type, source_id),
    FOREIGN KEY (chama_id) REFERENCES chamas (id) ON DELETE RESTRICT,
    FOREIGN KEY (posted_by_user_id) REFERENCES users (id) ON DELETE RESTRICT,
    FOREIGN KEY (reverses_transaction_id) REFERENCES ledger_transactions (id) ON DELETE RESTRICT
)
"""

SQLITE_ORIGINAL_ACCOUNTS = """
CREATE TABLE ledger_accounts_new (
    id CHAR(32) NOT NULL,
    chama_id CHAR(32) NOT NULL,
    code VARCHAR(32) NOT NULL,
    name VARCHAR(120) NOT NULL,
    account_type VARCHAR(20) NOT NULL,
    description VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_ledger_accounts_chama_code UNIQUE (chama_id, code),
    FOREIGN KEY (chama_id) REFERENCES chamas (id) ON DELETE RESTRICT
)
"""


def _downgrade_sqlite() -> None:
    _drop_guards_sqlite()
    original = {
        "ledger_entries": SQLITE_ORIGINAL_ENTRIES,
        "ledger_transactions": SQLITE_ORIGINAL_TRANSACTIONS,
        "ledger_accounts": SQLITE_ORIGINAL_ACCOUNTS,
    }
    copies = {
        "ledger_entries": """
            INSERT INTO ledger_entries_new
                (transaction_id, account_id, debit, credit, id, created_at, updated_at)
            SELECT transaction_id, account_id, debit, credit, id, created_at,
                   datetime(created_at) FROM ledger_entries
        """,
        "ledger_transactions": """
            INSERT INTO ledger_transactions_new
                (id, chama_id, source_type, source_id, description,
                 posted_by_user_id, reverses_transaction_id, created_at, updated_at)
            SELECT id, chama_id, source_type, source_id, description,
                   posted_by_user_id, reverses_transaction_id, created_at,
                   datetime(created_at) FROM ledger_transactions
        """,
        "ledger_accounts": """
            INSERT INTO ledger_accounts_new
                (id, chama_id, code, name, account_type, description,
                 created_at, updated_at)
            SELECT id, chama_id, code, name, account_type, description,
                   created_at, updated_at FROM ledger_accounts
        """,
    }
    for name in ("ledger_transactions", "ledger_accounts", "ledger_entries"):
        op.execute(sa.text(original[name]))
        op.execute(sa.text(copies[name]))
        op.execute(sa.text(f'DROP TABLE "{name}"'))
        op.execute(sa.text(f'ALTER TABLE "{name}_new" RENAME TO "{name}"'))
    op.execute(sa.text('CREATE INDEX "ix_ledger_transactions_chama_created" '
                       'ON ledger_transactions (chama_id, created_at)'))


def _downgrade_postgresql() -> None:
    for trigger in (
        "trg_chama_core_ledger_entries_balanced",
        "trg_chama_core_ledger_transaction_balanced",
        "trg_ledger_entries_no_delete",
        "trg_ledger_entries_no_update",
        "trg_ledger_transactions_no_delete",
        "trg_ledger_transactions_no_update",
    ):
        op.execute(sa.text(f'DROP TRIGGER IF EXISTS "{trigger}" ON ledger_transactions'))
        op.execute(sa.text(f'DROP TRIGGER IF EXISTS "{trigger}" ON ledger_entries'))
    op.execute(sa.text("DROP FUNCTION IF EXISTS chama_core_validate_ledger_entry_parent()"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS chama_core_validate_ledger_transaction()"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS chama_core_block_ledger_entries_write()"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS chama_core_block_ledger_transactions_write()"))

    op.drop_index("uq_ledger_transactions_reversal", table_name="ledger_transactions")
    op.add_column(
        "ledger_transactions",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    )
    op.drop_constraint("fk_ledger_transactions_reversal_chama", "ledger_transactions", type_="foreignkey")
    op.create_foreign_key(
        "ledger_transactions_reverses_transaction_id_fkey",
        "ledger_transactions",
        "ledger_transactions",
        ["reverses_transaction_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint("uq_ledger_transactions_chama_id", "ledger_transactions", type_="unique")

    op.add_column(
        "ledger_entries",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    )
    op.drop_constraint(
        "fk_ledger_entries_account_chama", "ledger_entries", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_ledger_entries_transaction_chama", "ledger_entries", type_="foreignkey"
    )
    op.create_foreign_key(
        "ledger_entries_account_id_fkey",
        "ledger_entries",
        "ledger_accounts",
        ["account_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "ledger_entries_transaction_id_fkey",
        "ledger_entries",
        "ledger_transactions",
        ["transaction_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_column("ledger_entries", "chama_id")

    op.drop_constraint("ck_ledger_accounts_non_blank", "ledger_accounts", type_="check")
    op.drop_constraint("ck_ledger_accounts_type", "ledger_accounts", type_="check")
    op.drop_constraint("uq_ledger_accounts_chama_id", "ledger_accounts", type_="unique")