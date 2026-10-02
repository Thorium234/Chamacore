"""add contributions.payment_date and payment_intents.requested_phone

Revision ID: d2bc49a77f51
Revises: 9a8b7c6d5e4f
Create Date: 2026-10-01 21:20:55.922540

Both columns are nullable and additive: ``contributions.payment_date`` records
the date a manually entered contribution was paid (informational only, it does
not affect ledger posting, which happens at confirmation), and
``payment_intents.requested_phone`` records an optional alternate prompt phone
when the intent is created; settlement remains bound to the intent's
membership.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d2bc49a77f51"
down_revision: Union[str, None] = "9a8b7c6d5e4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("contributions", sa.Column("payment_date", sa.Date(), nullable=True))
    op.add_column(
        "payment_intents",
        sa.Column("requested_phone", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("payment_intents", "requested_phone")
    op.drop_column("contributions", "payment_date")