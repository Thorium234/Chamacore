"""Member model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.membership import Membership


class Member(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "members"

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    government_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="member", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Member name={self.first_name} {self.last_name}>"