"""Ledger entry model (one debit/credit side of a ledger transaction)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Numeric,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.ledger_account import LedgerAccount
    from app.models.ledger_transaction import LedgerTransaction


class LedgerEntry(Base, UUIDMixin):
    __tablename__ = "ledger_entries"

    # chama_id is denormalized from the parent transaction for composite foreign
    # keys so the database rejects entries that join a transaction and an
    # account that belong to different Chamas (see __table_args__).
    chama_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    transaction_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    debit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"))
    credit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    transaction: Mapped["LedgerTransaction"] = relationship(
        back_populates="entries",
        primaryjoin="LedgerEntry.transaction_id == LedgerTransaction.id",
        foreign_keys="LedgerEntry.transaction_id",
    )
    account: Mapped["LedgerAccount"] = relationship(
        back_populates="entries",
        primaryjoin="LedgerEntry.account_id == LedgerAccount.id",
        foreign_keys="LedgerEntry.account_id",
    )

    __table_args__ = (
        CheckConstraint("debit >= 0 AND credit >= 0", name="ck_ledger_entries_non_negative"),
        CheckConstraint(
            "(debit > 0 AND credit = 0) OR (debit = 0 AND credit > 0)",
            name="ck_ledger_entries_single_side",
        ),
        ForeignKeyConstraint(
            ["chama_id", "transaction_id"],
            ["ledger_transactions.chama_id", "ledger_transactions.id"],
            ondelete="RESTRICT",
            name="fk_ledger_entries_transaction_chama",
        ),
        ForeignKeyConstraint(
            ["chama_id", "account_id"],
            ["ledger_accounts.chama_id", "ledger_accounts.id"],
            ondelete="RESTRICT",
            name="fk_ledger_entries_account_chama",
        ),
    )

    def __repr__(self) -> str:
        return f"<LedgerEntry debit={self.debit} credit={self.credit}>"