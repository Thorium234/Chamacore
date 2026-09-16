"""Ledger transaction model (financial transaction history)."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Uuid,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.chama import Chama
    from app.models.ledger_entry import LedgerEntry
    from app.models.user import User


class LedgerTransaction(Base, UUIDMixin):
    __tablename__ = "ledger_transactions"

    chama_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chamas.id", ondelete="RESTRICT"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    posted_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    reverses_transaction_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    chama: Mapped["Chama"] = relationship()
    posted_by: Mapped["User"] = relationship()
    reversal_of: Mapped["LedgerTransaction | None"] = relationship(
        remote_side="LedgerTransaction.id",
        foreign_keys="LedgerTransaction.reverses_transaction_id",
    )
    entries: Mapped[list["LedgerEntry"]] = relationship(back_populates="transaction", viewonly=True)

    __table_args__ = (
        UniqueConstraint("source_type", "source_id", name="uq_ledger_transactions_source"),
        UniqueConstraint("chama_id", "id", name="uq_ledger_transactions_chama_id"),
        ForeignKeyConstraint(
            ["chama_id", "reverses_transaction_id"],
            ["ledger_transactions.chama_id", "ledger_transactions.id"],
            ondelete="RESTRICT",
            name="fk_ledger_transactions_reversal_chama",
        ),
        Index("ix_ledger_transactions_chama_created", "chama_id", "created_at"),
        Index(
            "uq_ledger_transactions_reversal",
            "reverses_transaction_id",
            unique=True,
            sqlite_where=text("reverses_transaction_id IS NOT NULL"),
            postgresql_where=text("reverses_transaction_id IS NOT NULL"),
        ),
    )

    def __repr__(self) -> str:
        return f"<LedgerTransaction source={self.source_type}:{self.source_id}>"