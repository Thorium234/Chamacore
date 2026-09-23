"""Registration fee payment model (ADR-022)."""

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
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import RegistrationFeePaymentStatus

if TYPE_CHECKING:
    from app.models.membership import Membership
    from app.models.registration_fee import RegistrationFee
    from app.models.user import User


class RegistrationFeePayment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "registration_fee_payments"

    chama_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    fee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("registration_fees.id", ondelete="RESTRICT"), nullable=False
    )
    membership_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[RegistrationFeePaymentStatus] = mapped_column(
        Enum(
            RegistrationFeePaymentStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=RegistrationFeePaymentStatus.CONFIRMED,
    )
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    paid_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    fee: Mapped["RegistrationFee"] = relationship(back_populates="payments")
    membership: Mapped["Membership"] = relationship(back_populates="registration_fee_payments")
    recorded_by: Mapped["User"] = relationship()

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_registration_fee_payments_amount_positive"),
        ForeignKeyConstraint(
            ["chama_id", "membership_id"],
            ["memberships.chama_id", "memberships.id"],
            ondelete="RESTRICT",
            name="fk_registration_fee_payments_membership_chama",
        ),
        Index(
            "uq_registration_fee_payments_fee_confirmed",
            "fee_id",
            unique=True,
            sqlite_where=text("status = 'CONFIRMED'"),
            postgresql_where=text("status = 'CONFIRMED'"),
        ),
        Index("ix_registration_fee_payments_fee_status", "fee_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<RegistrationFeePayment amount={self.amount} status={self.status}>"