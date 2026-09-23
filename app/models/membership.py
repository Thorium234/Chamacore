"""Membership model."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import MembershipStatus, RoleName

if TYPE_CHECKING:
    from app.models.chama import Chama
    from app.models.contribution import Contribution
    from app.models.loan import Loan
    from app.models.member import Member
    from app.models.payout import Payout
    from app.models.registration_fee import RegistrationFee
    from app.models.registration_fee_payment import RegistrationFeePayment
    from app.models.share import Share


class Membership(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "memberships"

    chama_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chamas.id", ondelete="RESTRICT"), nullable=False)
    member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("members.id", ondelete="RESTRICT"), nullable=False)
    membership_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[MembershipStatus] = mapped_column(
        Enum(MembershipStatus, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=MembershipStatus.ACTIVE,
    )
    joined_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.now)

    chama: Mapped["Chama"] = relationship(back_populates="memberships", lazy="joined")
    member: Mapped["Member"] = relationship(back_populates="memberships", lazy="joined")
    roles: Mapped[list["Role"]] = relationship(
        secondary="membership_roles",
        lazy="selectin",
        order_by="Role.name",
    )
    registration_fee: Mapped["RegistrationFee | None"] = relationship(
        back_populates="membership", lazy="joined", uselist=False
    )
    contributions: Mapped[list["Contribution"]] = relationship(
        back_populates="membership", lazy="selectin"
    )
    shares: Mapped[list["Share"]] = relationship(back_populates="membership", lazy="selectin")
    loans: Mapped[list["Loan"]] = relationship(back_populates="membership", lazy="selectin")
    payouts: Mapped[list["Payout"]] = relationship(back_populates="membership", lazy="selectin")
    registration_fee_payments: Mapped[list["RegistrationFeePayment"]] = relationship(
        back_populates="membership", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("chama_id", "member_id", name="uq_memberships_chama_member"),
        UniqueConstraint("chama_id", "membership_number", name="uq_memberships_chama_number"),
        # Composite (chama_id, id) unique target for financial tables that
        # enforce Chama ownership of memberships at the database level.
        UniqueConstraint("chama_id", "id", name="uq_memberships_chama_id"),
    )

    def has_role(self, role_name: RoleName) -> bool:
        return any(role.name == role_name.value for role in self.roles)

    def __repr__(self) -> str:
        return f"<Membership number={self.membership_number} status={self.status}>"