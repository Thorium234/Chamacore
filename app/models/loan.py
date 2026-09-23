"""Loan model (ADR-020)."""

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
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import LoanStatus

if TYPE_CHECKING:
    from app.models.loan_repayment import LoanRepayment
    from app.models.membership import Membership
    from app.models.user import User


class Loan(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "loans"

    chama_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chamas.id", ondelete="RESTRICT"), nullable=False
    )
    membership_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    principal: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    interest_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[LoanStatus] = mapped_column(
        Enum(LoanStatus, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=LoanStatus.DRAFT,
    )
    application_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    approval_date: Mapped[datetime | None] = mapped_column(nullable=True)
    disbursement_date: Mapped[datetime | None] = mapped_column(nullable=True)
    maturity_date: Mapped[datetime | None] = mapped_column(nullable=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    disbursed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    membership: Mapped["Membership"] = relationship(back_populates="loans")
    approved_by: Mapped["User | None"] = relationship(foreign_keys=[approved_by_user_id])
    disbursed_by: Mapped["User | None"] = relationship(foreign_keys=[disbursed_by_user_id])
    recorded_by: Mapped["User"] = relationship(foreign_keys=[recorded_by_user_id])
    repayments: Mapped[list["LoanRepayment"]] = relationship(
        back_populates="loan", lazy="selectin"
    )

    __table_args__ = (
        CheckConstraint("principal > 0", name="ck_loans_principal_positive"),
        CheckConstraint("interest_rate >= 0", name="ck_loans_interest_rate_non_negative"),
        CheckConstraint("term_months >= 3 AND term_months <= 12", name="ck_loans_term_months_range"),
        UniqueConstraint("chama_id", "id", name="uq_loans_chama_id"),
        ForeignKeyConstraint(
            ["chama_id", "membership_id"],
            ["memberships.chama_id", "memberships.id"],
            ondelete="RESTRICT",
            name="fk_loans_membership_chama",
        ),
        Index("ix_loans_chama_status", "chama_id", "status"),
        Index("ix_loans_membership_status", "membership_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Loan status={self.status} principal={self.principal}>"