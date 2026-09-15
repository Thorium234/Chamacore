"""Contribution model."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import ContributionStatus

if TYPE_CHECKING:
    from app.models.membership import Membership
    from app.models.share import Share
    from app.models.user import User


class Contribution(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "contributions"

    membership_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memberships.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    period: Mapped[str] = mapped_column(String(7), nullable=False)
    status: Mapped[ContributionStatus] = mapped_column(
        Enum(ContributionStatus, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=ContributionStatus.PENDING,
    )
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    membership: Mapped["Membership"] = relationship(back_populates="contributions")
    recorded_by: Mapped["User"] = relationship()
    shares: Mapped[list["Share"]] = relationship(back_populates="contribution")

    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_contributions_amount_non_negative"),
        Index(
            "uq_contributions_membership_period_open",
            "membership_id",
            "period",
            unique=True,
            sqlite_where=text("status != 'REVERSED'"),
            postgresql_where=text("status <> 'REVERSED'"),
        ),
    )

    def __repr__(self) -> str:
        return f"<Contribution period={self.period} amount={self.amount} status={self.status}>"