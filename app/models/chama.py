"""Chama model."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import ChamaStatus

if TYPE_CHECKING:
    from app.models.membership import Membership
    from app.models.membership_sequence import MembershipSequence
    from app.models.user import User


class Chama(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "chamas"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    registration_fee_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0")
    )
    status: Mapped[ChamaStatus] = mapped_column(
        Enum(ChamaStatus, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=ChamaStatus.ACTIVE,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    created_by: Mapped["User"] = relationship()
    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="chama", lazy="selectin"
    )
    sequence: Mapped["MembershipSequence | None"] = relationship(
        back_populates="chama", lazy="joined", uselist=False
    )

    __table_args__ = (
        CheckConstraint(
            "registration_fee_amount >= 0", name="ck_chamas_registration_fee_amount_non_negative"
        ),
    )

    def __repr__(self) -> str:
        return f"<Chama name={self.name!r} status={self.status}>"