"""MembershipRole association model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    pass


class MembershipRole(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "membership_roles"

    membership_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memberships.id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("membership_id", "role_id", name="uq_membership_roles_membership_role"),
    )