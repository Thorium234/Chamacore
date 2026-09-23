"""Loan repayment model (ADR-020 repayment allocation)."""

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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import LoanRepaymentStatus

if TYPE_CHECKING:
    from app.models.loan import Loan
    from app.models.user import User


class LoanRepayment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "loan_repayments"

    chama_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    loan_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    principal_portion: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    interest_portion: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[LoanRepaymentStatus] = mapped_column(
        Enum(
            LoanRepaymentStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=LoanRepaymentStatus.CONFIRMED,
    )
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    loan: Mapped["Loan"] = relationship(back_populates="repayments")
    recorded_by: Mapped["User"] = relationship()

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_loan_repayments_amount_positive"),
        CheckConstraint(
            "principal_portion >= 0 AND interest_portion >= 0",
            name="ck_loan_repayments_portions_non_negative",
        ),
        CheckConstraint(
            "amount = principal_portion + interest_portion",
            name="ck_loan_repayments_amount_split",
        ),
        ForeignKeyConstraint(
            ["chama_id", "loan_id"],
            ["loans.chama_id", "loans.id"],
            ondelete="RESTRICT",
            name="fk_loan_repayments_loan_chama",
        ),
        Index("ix_loan_repayments_loan_status", "loan_id", "status"),
        Index("ix_loan_repayments_loan_created", "loan_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<LoanRepayment amount={self.amount} "
            f"principal={self.principal_portion} interest={self.interest_portion} "
            f"status={self.status}>"
        )