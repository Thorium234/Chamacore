"""RegistrationFee model."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import RegistrationFeeStatus

if TYPE_CHECKING:
    from app.models.membership import Membership
    from app.models.registration_fee_payment import RegistrationFeePayment


class RegistrationFee(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "registration_fees"

    membership_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memberships.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[RegistrationFeeStatus] = mapped_column(
        Enum(RegistrationFeeStatus, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=RegistrationFeeStatus.OWED,
    )

    membership: Mapped["Membership"] = relationship(back_populates="registration_fee")
    payments: Mapped[list["RegistrationFeePayment"]] = relationship(back_populates="fee")

    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_registration_fees_amount_non_negative"),
        UniqueConstraint("membership_id", name="uq_registration_fees_membership_id"),
    )

    def __repr__(self) -> str:
        return f"<RegistrationFee amount={self.amount} status={self.status}>"