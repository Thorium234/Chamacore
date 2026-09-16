"""add V2 financial ledger tables

Revision ID: c7d8e9f0a1b2
Revises: a1b2c3d4e5f6
Create Date: 2026-09-16 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    timestamp_cols = (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    )

    op.create_table(
        "ledger_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chama_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "account_type",
            sa.Enum(
                "ASSET",
                "LIABILITY",
                "EQUITY",
                "REVENUE",
                "EXPENSE",
                name="ledger_account_type",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("description", sa.String(length=255), nullable=True),
        *timestamp_cols,
        sa.ForeignKeyConstraint(["chama_id"], ["chamas.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chama_id", "code", name="uq_ledger_accounts_chama_code"),
    )

    op.create_table(
        "ledger_transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chama_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("posted_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("reverses_transaction_id", sa.Uuid(), nullable=True),
        *timestamp_cols,
        sa.ForeignKeyConstraint(["chama_id"], ["chamas.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["posted_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reverses_transaction_id"], ["ledger_transactions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_type", "source_id", name="uq_ledger_transactions_source"),
    )
    op.create_index(
        "ix_ledger_transactions_chama_created",
        "ledger_transactions",
        ["chama_id", "created_at"],
    )

    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("debit", sa.Numeric(18, 2), nullable=False),
        sa.Column("credit", sa.Numeric(18, 2), nullable=False),
        *timestamp_cols,
        sa.CheckConstraint("debit >= 0 AND credit >= 0", name="ck_ledger_entries_non_negative"),
        sa.CheckConstraint(
            "(debit > 0 AND credit = 0) OR (debit = 0 AND credit > 0)",
            name="ck_ledger_entries_single_side",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["ledger_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["transaction_id"], ["ledger_transactions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("ledger_entries")
    op.drop_index("ix_ledger_transactions_chama_created", table_name="ledger_transactions")
    op.drop_table("ledger_transactions")
    op.drop_table("ledger_accounts")