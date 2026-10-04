"""optionally bootstrap the first platform administrator from runtime secrets

Revision ID: b6d4f82c1a90
Revises: a3e9200e3b6d
Create Date: 2026-10-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

from app.core.config import get_settings
from app.db.bootstrap_platform_admin import ensure_bootstrap_platform_admin

revision: str = "b6d4f82c1a90"
down_revision: Union[str, None] = "a3e9200e3b6d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Credentials are read from ignored .env/runtime secrets. Missing all
    # bootstrap settings is allowed; the idempotent fallback command remains
    # available if this revision has already run without them.
    ensure_bootstrap_platform_admin(op.get_bind(), get_settings())


def downgrade() -> None:
    # Keep the provisioned identity and grant. They may have been used or had
    # their password changed after creation; deleting them is not a safe schema
    # rollback operation.
    pass
