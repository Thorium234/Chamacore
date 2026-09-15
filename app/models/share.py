"""Share model."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import ShareStatus

if TYPE_CHECKING:
    from app.models.contribution import Contribution
    from app.models.membership import Membership


class Share(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "shares"

    membership_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memberships.id", ondelete="RESTRICT"), nullable=False
    )
    contribution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contributions.id", ondelete="RESTRICT"), nullable=False
    )
    units: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    status: Mapped[ShareStatus] = mapped_column(
        Enum(ShareStatus, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=ShareStatus.ACTIVE,
    )

    membership: Mapped["Membership"] = relationship(back_populates="shares")
    contribution: Mapped["Contribution"] = relationship(back_populates="shares")

    __table_args__ = (
        CheckConstraint("units >= 0", name="ck_shares_units_non_negative"),
        UniqueConstraint("contribution_id", name="uq_shares_contribution_id"),
    )

    def __repr__(self) -> str:
        return f"<Share units={self.units} status={self.status}>"