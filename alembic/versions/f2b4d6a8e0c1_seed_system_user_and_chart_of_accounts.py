"""seed system user and default chart of accounts (OQ-012, ADR-019)

Revision ID: f2b4d6a8e0c1
Revises: e4f5a6b7c8d9
Create Date: 2026-09-22 00:00:00.000000

"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.db.bootstrap import SYSTEM_USER_EMAIL, SYSTEM_USER_UUID
from app.services.ledger import CHART_ACCOUNTS

revision: str = "f2b4d6a8e0c1"
down_revision: Union[str, None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO users (id, email, password_hash, is_active) "
            "VALUES (:id, :email, :password_hash, 1) "
            "ON CONFLICT (email) DO NOTHING"
        ),
        {
            "id": str(SYSTEM_USER_UUID),
            "email": SYSTEM_USER_EMAIL,
            "password_hash": "!system-account-no-login!",
        },
    )
    chama_ids = [row[0] for row in bind.execute(sa.text("SELECT id FROM chamas"))]
    for chama_id in chama_ids:
        for code, name, account_type, description in CHART_ACCOUNTS:
            bind.execute(
                sa.text(
                    "INSERT INTO ledger_accounts "
                    "(id, chama_id, code, name, account_type, description) "
                    "VALUES (:id, :chama_id, :code, :name, :account_type, :description) "
                    "ON CONFLICT (chama_id, code) DO NOTHING"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "chama_id": str(chama_id),
                    "code": code,
                    "name": name,
                    "account_type": account_type.value,
                    "description": description,
                },
            )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM users WHERE id = :id"),
        {"id": str(SYSTEM_USER_UUID)},
    )
    for code, _, _, _ in CHART_ACCOUNTS:
        bind.execute(
            sa.text("DELETE FROM ledger_accounts WHERE code = :code"),
            {"code": code},
        )