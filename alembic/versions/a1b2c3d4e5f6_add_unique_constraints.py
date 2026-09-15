"""add unique constraints for users, registration_fees, shares

Revision ID: a1b2c3d4e5f6
Revises: 68ce987eb072
Create Date: 2026-09-15 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "68ce987eb072"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # P0: One Member may be linked to only one User account.
    with op.batch_alter_table("users") as batch_op:
        batch_op.create_unique_constraint("uq_users_member_id", ["member_id"])

    # P1: One registration fee per membership.
    with op.batch_alter_table("registration_fees") as batch_op:
        batch_op.create_unique_constraint("uq_registration_fees_membership_id", ["membership_id"])

    # P1: One share per confirmed contribution.
    with op.batch_alter_table("shares") as batch_op:
        batch_op.create_unique_constraint("uq_shares_contribution_id", ["contribution_id"])


def downgrade() -> None:
    with op.batch_alter_table("shares") as batch_op:
        batch_op.drop_constraint("uq_shares_contribution_id", type_="unique")

    with op.batch_alter_table("registration_fees") as batch_op:
        batch_op.drop_constraint("uq_registration_fees_membership_id", type_="unique")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_users_member_id", type_="unique")
