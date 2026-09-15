"""Transactional membership-number sequence table."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.chama import Chama


class MembershipSequence(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "membership_sequences"

    chama_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chamas.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    next_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    chama: Mapped["Chama"] = relationship(back_populates="sequence")

    def __repr__(self) -> str:
        return f"<MembershipSequence chama={self.chama_id} next={self.next_number}>"