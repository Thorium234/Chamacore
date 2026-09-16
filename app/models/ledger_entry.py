"""Ledger entry model (one debit/credit side of a ledger transaction)."""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.ledger_account import LedgerAccount
    from app.models.ledger_transaction import LedgerTransaction


class LedgerEntry(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ledger_entries"

    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ledger_transactions.id", ondelete="RESTRICT"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ledger_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    debit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"))
    credit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"))

    transaction: Mapped["LedgerTransaction"] = relationship(back_populates="entries")
    account: Mapped["LedgerAccount"] = relationship(back_populates="entries")

    __table_args__ = (
        CheckConstraint("debit >= 0 AND credit >= 0", name="ck_ledger_entries_non_negative"),
        CheckConstraint("(debit > 0 AND credit = 0) OR (debit = 0 AND credit > 0)", name="ck_ledger_entries_single_side"),
    )

    def __repr__(self) -> str:
        return f"<LedgerEntry debit={self.debit} credit={self.credit}>"