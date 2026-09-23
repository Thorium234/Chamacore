"""Payout model (ADR-021)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import PayoutStatus

if TYPE_CHECKING:
    from app.models.membership import Membership
    from app.models.user import User


class Payout(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "payouts"

    chama_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chamas.id", ondelete="RESTRICT"), nullable=False
    )
    membership_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[PayoutStatus] = mapped_column(
        Enum(PayoutStatus, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=PayoutStatus.REQUESTED,
    )
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    processed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    completed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    membership: Mapped["Membership"] = relationship(back_populates="payouts")
    requested_by: Mapped["User"] = relationship(foreign_keys=[requested_by_user_id])
    approved_by: Mapped["User | None"] = relationship(foreign_keys=[approved_by_user_id])
    processed_by: Mapped["User | None"] = relationship(foreign_keys=[processed_by_user_id])
    completed_by: Mapped["User | None"] = relationship(foreign_keys=[completed_by_user_id])

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payouts_amount_positive"),
        UniqueConstraint("chama_id", "id", name="uq_payouts_chama_id"),
        ForeignKeyConstraint(
            ["chama_id", "membership_id"],
            ["memberships.chama_id", "memberships.id"],
            ondelete="RESTRICT",
            name="fk_payouts_membership_chama",
        ),
        Index("ix_payouts_chama_status", "chama_id", "status"),
        Index("ix_payouts_membership_status", "membership_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Payout amount={self.amount} status={self.status}>"