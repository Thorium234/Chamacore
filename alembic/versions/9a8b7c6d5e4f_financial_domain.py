"""financial domain: loans, repayments, payouts, fee payments, audit events

Revision ID: 9a8b7c6d5e4f
Revises: a1f0c3e5b7d9
Create Date: 2026-09-23 00:00:00.000000

Implements the approved financial-domain decisions:

- ADR-020: loans + loan repayments (status machine, term/interest checks,
  supports repayments referencing ``loans (chama_id, id)``).
- ADR-021: payouts (status machine, share-value/cash limits).
- ADR-022: registration fee payments (fixed-fee cash settlement with a
  partial unique index on the confirmed payment per fee).
- ADR-023: append-only ``audit_events`` (UPDATE/DELETE guard triggers).

Backfills the two new default ledger accounts (``1100`` Loans Receivable,
``5000`` Interest Income) for Chamas created before this pass, and adds the
composite unique ``(chama_id, id)`` on memberships that the financial tables
reference through Chama-scoped foreign keys.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.db.audit_guards import create_audit_guards
from app.models.enums import LedgerAccountType
from app.services.ledger import INTEREST_INCOME_CODE, LOANS_RECEIVABLE_CODE

revision: str = "9a8b7c6d5e4f"
down_revision: Union[str, None] = "a1f0c3e5b7d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_ACCOUNTS = (
    (LOANS_RECEIVABLE_CODE, "Loans Receivable", LedgerAccountType.ASSET, "Outstanding loan principal owed by members (ADR-020)"),
    (INTEREST_INCOME_CODE, "Interest Income", LedgerAccountType.REVENUE, "Service interest earned on member loans (ADR-020)"),
)

TIMESTAMP_COLS = (
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


def _make_status_column(name, values, default, length=20):
    return sa.Column(
        name,
        sa.Enum(*values, name=name, native_enum=False, length=length),
        nullable=False,
        server_default=sa.text(f"'{default}'"),
    )


def _backfill_new_accounts() -> None:
    bind = op.get_bind()
    chama_ids = [row[0] for row in bind.execute(sa.text("SELECT id FROM chamas"))]
    for chama_id in chama_ids:
        for code, name, account_type, description in NEW_ACCOUNTS:
            bind.execute(
                sa.text(
                    "INSERT INTO ledger_accounts "
                    "(id, chama_id, code, name, account_type, description) "
                    "VALUES (:id, :chama_id, :code, :name, :account_type, :description) "
                    "ON CONFLICT (chama_id, code) DO NOTHING"
                ),
                {
                    "id": str(__import__("uuid").uuid4()),
                    "chama_id": str(chama_id),
                    "code": code,
                    "name": name,
                    "account_type": account_type.value,
                    "description": description,
                },
            )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("memberships") as batch_op:
            batch_op.create_unique_constraint(
                "uq_memberships_chama_id", ["chama_id", "id"]
            )
    else:
        op.create_unique_constraint(
            "uq_memberships_chama_id", "memberships", ["chama_id", "id"]
        )

    op.create_table(
        "loans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chama_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("principal", sa.Numeric(18, 2), nullable=False),
        sa.Column("interest_rate", sa.Numeric(6, 4), nullable=False),
        sa.Column("term_months", sa.Integer(), nullable=False),
        _make_status_column(
            "status",
            ["DRAFT", "SUBMITTED", "APPROVED", "DISBURSED", "PARTIALLY_REPAID", "REPAID", "REJECTED", "CANCELLED"],
            "DRAFT",
        ),
        sa.Column(
            "application_date",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("approval_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disbursement_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("maturity_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("disbursed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("recorded_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        *TIMESTAMP_COLS,
        sa.CheckConstraint("principal > 0", name="ck_loans_principal_positive"),
        sa.CheckConstraint("interest_rate >= 0", name="ck_loans_interest_rate_non_negative"),
        sa.CheckConstraint("term_months >= 3 AND term_months <= 12", name="ck_loans_term_months_range"),
        sa.ForeignKeyConstraint(["chama_id"], ["chamas.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["chama_id", "membership_id"],
            ["memberships.chama_id", "memberships.id"],
            ondelete="RESTRICT",
            name="fk_loans_membership_chama",
        ),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["disbursed_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chama_id", "id", name="uq_loans_chama_id"),
    )
    op.create_index("ix_loans_chama_status", "loans", ["chama_id", "status"])
    op.create_index("ix_loans_membership_status", "loans", ["membership_id", "status"])

    op.create_table(
        "loan_repayments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chama_id", sa.Uuid(), nullable=False),
        sa.Column("loan_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("principal_portion", sa.Numeric(18, 2), nullable=False),
        sa.Column("interest_portion", sa.Numeric(18, 2), nullable=False),
        _make_status_column("status", ["CONFIRMED", "REVERSED"], "CONFIRMED"),
        sa.Column("recorded_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        *TIMESTAMP_COLS,
        sa.CheckConstraint("amount > 0", name="ck_loan_repayments_amount_positive"),
        sa.CheckConstraint(
            "principal_portion >= 0 AND interest_portion >= 0",
            name="ck_loan_repayments_portions_non_negative",
        ),
        sa.CheckConstraint(
            "amount = principal_portion + interest_portion",
            name="ck_loan_repayments_amount_split",
        ),
        sa.ForeignKeyConstraint(
            ["chama_id", "loan_id"],
            ["loans.chama_id", "loans.id"],
            ondelete="RESTRICT",
            name="fk_loan_repayments_loan_chama",
        ),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_loan_repayments_loan_status", "loan_repayments", ["loan_id", "status"])
    op.create_index("ix_loan_repayments_loan_created", "loan_repayments", ["loan_id", "created_at"])

    op.create_table(
        "payouts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chama_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        _make_status_column(
            "status",
            ["REQUESTED", "APPROVED", "PROCESSING", "COMPLETED", "REJECTED", "FAILED", "REVERSED"],
            "REQUESTED",
        ),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("approved_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("processed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("completed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("failure_reason", sa.String(length=500), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *TIMESTAMP_COLS,
        sa.CheckConstraint("amount > 0", name="ck_payouts_amount_positive"),
        sa.ForeignKeyConstraint(["chama_id"], ["chamas.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["chama_id", "membership_id"],
            ["memberships.chama_id", "memberships.id"],
            ondelete="RESTRICT",
            name="fk_payouts_membership_chama",
        ),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["processed_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["completed_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chama_id", "id", name="uq_payouts_chama_id"),
    )
    op.create_index("ix_payouts_chama_status", "payouts", ["chama_id", "status"])
    op.create_index("ix_payouts_membership_status", "payouts", ["membership_id", "status"])

    op.create_table(
        "registration_fee_payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chama_id", sa.Uuid(), nullable=False),
        sa.Column("fee_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        _make_status_column("status", ["CONFIRMED", "REVERSED"], "CONFIRMED"),
        sa.Column("recorded_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "paid_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        *TIMESTAMP_COLS,
        sa.CheckConstraint("amount > 0", name="ck_registration_fee_payments_amount_positive"),
        sa.ForeignKeyConstraint(["fee_id"], ["registration_fees.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["chama_id", "membership_id"],
            ["memberships.chama_id", "memberships.id"],
            ondelete="RESTRICT",
            name="fk_registration_fee_payments_membership_chama",
        ),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_registration_fee_payments_fee_confirmed",
        "registration_fee_payments",
        ["fee_id"],
        unique=True,
        sqlite_where=sa.text("status = 'CONFIRMED'"),
        postgresql_where=sa.text("status = 'CONFIRMED'"),
    )
    op.create_index(
        "ix_registration_fee_payments_fee_status",
        "registration_fee_payments",
        ["fee_id", "status"],
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chama_id", sa.Uuid(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["chama_id"], ["chamas.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_chama_created", "audit_events", ["chama_id", "created_at"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_resource", "audit_events", ["resource_type", "resource_id"])

    _backfill_new_accounts()
    create_audit_guards(op.get_bind())


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("memberships") as batch_op:
            batch_op.drop_constraint("uq_memberships_chama_id", type_="unique")
    else:
        op.drop_constraint("uq_memberships_chama_id", "memberships", type_="unique")

    op.drop_index("ix_audit_events_resource", table_name="audit_events")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_index("ix_audit_events_chama_created", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index(
        "ix_registration_fee_payments_fee_status", table_name="registration_fee_payments"
    )
    op.drop_index(
        "uq_registration_fee_payments_fee_confirmed", table_name="registration_fee_payments"
    )
    op.drop_table("registration_fee_payments")

    op.drop_index("ix_payouts_membership_status", table_name="payouts")
    op.drop_index("ix_payouts_chama_status", table_name="payouts")
    op.drop_table("payouts")

    op.drop_index("ix_loan_repayments_loan_created", table_name="loan_repayments")
    op.drop_index("ix_loan_repayments_loan_status", table_name="loan_repayments")
    op.drop_table("loan_repayments")

    op.drop_index("ix_loans_membership_status", table_name="loans")
    op.drop_index("ix_loans_chama_status", table_name="loans")
    op.drop_table("loans")

    bind.execute(
        sa.text("DELETE FROM ledger_accounts WHERE code IN (:lower, :higher)"),
        {"lower": LOANS_RECEIVABLE_CODE, "higher": INTEREST_INCOME_CODE},
    )