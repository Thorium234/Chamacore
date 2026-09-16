"""add V3 payment tables

Revision ID: e4f5a6b7c8d9
Revises: d1e2f3a4b5c6
Create Date: 2026-09-16 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, None] = "d1e2f3a4b5c6"
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
        "payment_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chama_id", sa.Uuid(), nullable=False),
        sa.Column(
            "provider_code",
            sa.Enum("JENGA", "DARAJA", name="payment_provider_code", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column(
            "environment",
            sa.Enum("SANDBOX", "PRODUCTION", name="payment_environment", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING_VALIDATION", "ACTIVE", "DISABLED", "INVALID",
                name="payment_connection_status", native_enum=False, length=30,
            ),
            nullable=False,
        ),
        sa.Column("encrypted_credentials", sa.Text(), nullable=False),
        sa.Column("encryption_key_version", sa.Integer(), nullable=False),
        sa.Column("credential_version", sa.Integer(), nullable=False),
        sa.Column("masked_account_identifier", sa.String(length=120), nullable=False),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_validation_error_code", sa.String(length=64), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=False),
        *timestamp_cols,
        sa.ForeignKeyConstraint(["chama_id"], ["chamas.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "chama_id", "provider_code", "environment",
            name="uq_payment_connections_chama_provider_environment",
        ),
    )

    op.create_table(
        "payment_connection_audit",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "action",
            sa.Enum(
                "CREATED", "CREDENTIALS_REPLACED", "VALIDATED", "TESTED",
                "ENABLED", "DISABLED", "DELETED",
                name="payment_connection_audit_action", native_enum=False, length=30,
            ),
            nullable=False,
        ),
        sa.Column(
            "previous_status",
            sa.Enum(
                "PENDING_VALIDATION", "ACTIVE", "DISABLED", "INVALID",
                name="payment_connection_status", native_enum=False, length=30,
            ),
            nullable=True,
        ),
        sa.Column(
            "new_status",
            sa.Enum(
                "PENDING_VALIDATION", "ACTIVE", "DISABLED", "INVALID",
                name="payment_connection_status", native_enum=False, length=30,
            ),
            nullable=True,
        ),
        sa.Column("credential_version", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["connection_id"], ["payment_connections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "payment_intents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chama_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("contribution_id", sa.Uuid(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
        ),
        sa.Column("purpose", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING", "PROCESSING", "SUCCEEDED", "FAILED",
                name="payment_intent_status", native_enum=False, length=20,
            ),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("idempotency_payload_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "last_transition_source",
            sa.Enum(
                "CLIENT", "PROVIDER_CALLBACK", "STATUS_QUERY", "SYSTEM",
                name="payment_transfer_source", native_enum=False, length=30,
            ),
            nullable=False,
        ),
        sa.Column("last_transition_by_user_id", sa.Uuid(), nullable=True),
        *timestamp_cols,
        sa.CheckConstraint("amount > 0", name="ck_payment_intents_amount_positive"),
        sa.CheckConstraint("currency = upper(currency)", name="ck_payment_intents_currency_upper"),
        sa.ForeignKeyConstraint(["chama_id"], ["chamas.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["last_transition_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["membership_id"], ["memberships.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "chama_id", "idempotency_key",
            name="uq_payment_intents_chama_key",
        ),
    )

    op.create_table(
        "payment_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("payment_intent_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("provider_request_id", sa.String(length=255), nullable=True),
        sa.Column("provider_transaction_id", sa.String(length=255), nullable=True),
        sa.Column("client_reference", sa.String(length=255), nullable=False),
        sa.Column("retryable", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column(
            "status",
            sa.Enum(
                "INITIATED", "SUCCEEDED", "FAILED", "TIMEOUT", "UNKNOWN",
                name="payment_attempt_status", native_enum=False, length=20,
            ),
            nullable=False,
        ),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_message_safe", sa.String(length=500), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_transition_source",
            sa.Enum(
                "CLIENT", "PROVIDER_CALLBACK", "STATUS_QUERY", "SYSTEM",
                name="payment_transfer_source", native_enum=False, length=30,
            ),
            nullable=False,
        ),
        *timestamp_cols,
        sa.CheckConstraint("attempt_number >= 1", name="ck_payment_attempts_number_positive"),
        sa.CheckConstraint(
            "status IN ('SUCCEEDED', 'FAILED') OR completed_at IS NULL",
            name="ck_payment_attempts_completed_only_final",
        ),
        sa.ForeignKeyConstraint(["connection_id"], ["payment_connections.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["payment_intent_id"], ["payment_intents.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "payment_intent_id", "attempt_number",
            name="uq_payment_attempts_intent_number",
        ),
        sa.UniqueConstraint(
            "connection_id", "client_reference",
            name="uq_payment_attempts_connection_reference",
        ),
    )

    op.create_table(
        "provider_transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("payment_attempt_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("provider_request_id", sa.String(length=255), nullable=True),
        sa.Column("provider_transaction_id", sa.String(length=255), nullable=True),
        sa.Column("provider_event_id", sa.String(length=255), nullable=True),
        sa.Column(
            "normalized_status",
            sa.Enum(
                "PENDING", "SUCCEEDED", "FAILED", "UNKNOWN",
                name="provider_transaction_status", native_enum=False, length=20,
            ),
            nullable=False,
        ),
        sa.Column("raw_status", sa.String(length=100), nullable=True),
        sa.Column("last_queried_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_cols,
        sa.ForeignKeyConstraint(["connection_id"], ["payment_connections.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["payment_attempt_id"], ["payment_attempts.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "payment_attempt_id", name="uq_provider_transactions_attempt"
        ),
    )
    op.create_index(
        "uq_provider_transactions_request_id",
        "provider_transactions",
        ["provider_request_id"],
        unique=True,
        sqlite_where=sa.text("provider_request_id IS NOT NULL"),
        postgresql_where=sa.text("provider_request_id IS NOT NULL"),
    )
    op.create_index(
        "uq_provider_transactions_txn_id",
        "provider_transactions",
        ["provider_transaction_id"],
        unique=True,
        sqlite_where=sa.text("provider_transaction_id IS NOT NULL"),
        postgresql_where=sa.text("provider_transaction_id IS NOT NULL"),
    )

    op.create_table(
        "payment_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column(
            "provider_code",
            sa.Enum("JENGA", "DARAJA", name="payment_provider_code", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column(
            "environment",
            sa.Enum("SANDBOX", "PRODUCTION", name="payment_environment", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("provider_event_id", sa.String(length=255), nullable=True),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("raw_payload", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "RECEIVED", "PROCESSED", "DEDUPLICATED", "REJECTED",
                "UNPROCESSABLE", "DISAGREEMENT",
                name="payment_event_status", native_enum=False, length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_transition_source", sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(["connection_id"], ["payment_connections.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_payment_events_connection_event",
        "payment_events",
        ["connection_id", "provider_event_id"],
        unique=True,
        sqlite_where=sa.text("provider_event_id IS NOT NULL"),
        postgresql_where=sa.text("provider_event_id IS NOT NULL"),
    )
    op.create_index("ix_payment_events_status", "payment_events", ["status"])


def downgrade() -> None:
    op.drop_index("ix_payment_events_status", table_name="payment_events")
    op.drop_index("uq_payment_events_connection_event", table_name="payment_events")
    op.drop_table("payment_events")
    op.drop_index("uq_provider_transactions_request_id", table_name="provider_transactions")
    op.drop_index("uq_provider_transactions_txn_id", table_name="provider_transactions")
    op.drop_table("provider_transactions")
    op.drop_table("payment_attempts")
    op.drop_table("payment_intents")
    op.drop_table("payment_connection_audit")
    op.drop_table("payment_connections")