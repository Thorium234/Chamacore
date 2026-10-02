"""platform admin, notifications, and forced password change

Adds the cross-Chama platform administration surface (PLATFORM_ADMIN grants and
the Chama PENDING/ACTIVE/SUSPENDED/DISSOLVED lifecycle), the in-app
notification feed derived from business audit events, and
``users.must_change_password`` with a change-password endpoint.

Revision ID: a3e9200e3b6d
Revises: d2bc49a77f51
Create Date: 2026-10-02 11:03:01.684305

"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3e9200e3b6d"
down_revision: Union[str, None] = "d2bc49a77f51"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLE_TABLE = "roles"
PLATFORM_ADMIN_ROLE_UUID = uuid.UUID("3f9a1c74-5d2e-4b86-9a17-8c0e2d4f6b31")


def upgrade() -> None:
    op.create_table(
        "user_platform_roles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "CHAIRPERSON",
                "TREASURER",
                "SECRETARY",
                "MEMBER",
                "PLATFORM_ADMIN",
                name="rolename",
                native_enum=False,
                length=30,
            ),
            nullable=False,
        ),
        sa.Column("granted_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["granted_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "role", name="uq_user_platform_roles_user_role"),
    )

    # Seed the PLATFORM_ADMIN role so grants reference a real role row.
    bind = op.get_bind()
    bind.execute(
        sa.text(
            f"INSERT INTO {ROLE_TABLE} (id, name) "
            "VALUES (:id, :name) ON CONFLICT (name) DO NOTHING"
        ),
        {"id": str(PLATFORM_ADMIN_ROLE_UUID), "name": "PLATFORM_ADMIN"},
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "channel",
            sa.Enum(
                "IN_APP",
                name="notificationchannel",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("chama_id", sa.Uuid(), nullable=True),
        sa.Column("resource_type", sa.Text(), nullable=True),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["chama_id"], ["chamas.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notifications_user_created",
        "notifications",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_user_unread",
        "notifications",
        ["user_id", "is_read"],
        unique=False,
    )

    # Existing accounts are not forced to rotate; only accounts a platform
    # admin flags later carry this.
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "must_change_password")
    op.drop_index("ix_notifications_user_unread", table_name="notifications")
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_table("notifications")
    op.drop_table("user_platform_roles")
    bind = op.get_bind()
    bind.execute(
        sa.text(f"DELETE FROM {ROLE_TABLE} WHERE name = :name"),
        {"name": "PLATFORM_ADMIN"},
    )