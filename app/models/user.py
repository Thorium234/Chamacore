"""User model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.member import Member


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("members.id", ondelete="RESTRICT"), nullable=True, unique=True
    )

    member: Mapped["Member | None"] = relationship(lazy="joined")

    @property
    def can_create_chama(self) -> bool:
        """Whether this identity has never been enrolled in a Chama.

        Creation is reserved for an account whose member identity has no
        existing membership. This prevents a Chama member from creating a new
        group under the same registered phone-number identity.
        """
        return self.member is None or not self.member.memberships

    def __repr__(self) -> str:
        return f"<User email={self.email!r}>"
