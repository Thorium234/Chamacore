"""Global platform-role assignment for a user (platform administration).

Chama-scoped roles live on ``membership_roles``. ``PLATFORM_ADMIN`` is not a
Chama role: it grants cross-Chama visibility on the ``/platform`` endpoints, so
it is stored here against the user rather than against a membership.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin
from app.models.enums import RoleName

if TYPE_CHECKING:
    from app.models.user import User


class UserPlatformRole(Base, UUIDMixin):
    __tablename__ = "user_platform_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[RoleName] = mapped_column(
        Enum(RoleName, native_enum=False, length=30, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["User"] = relationship(foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint("user_id", "role", name="uq_user_platform_roles_user_role"),
    )

    def __repr__(self) -> str:
        return f"<UserPlatformRole user={self.user_id} role={self.role}>"