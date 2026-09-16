"""Ledger account model."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import LedgerAccountType

if TYPE_CHECKING:
    from app.models.chama import Chama
    from app.models.ledger_entry import LedgerEntry


class LedgerAccount(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ledger_accounts"

    chama_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chamas.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_type: Mapped[LedgerAccountType] = mapped_column(
        Enum(
            LedgerAccountType,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    chama: Mapped["Chama"] = relationship()
    entries: Mapped[list["LedgerEntry"]] = relationship(back_populates="account")

    __table_args__ = (
        UniqueConstraint("chama_id", "code", name="uq_ledger_accounts_chama_code"),
        # Name/id unique target for ledger_entries composite ownership foreign keys.
        UniqueConstraint("chama_id", "id", name="uq_ledger_accounts_chama_id"),
        CheckConstraint(
            "account_type IN ('ASSET', 'LIABILITY', 'EQUITY', 'REVENUE', 'EXPENSE')",
            name="ck_ledger_accounts_type",
        ),
        CheckConstraint(
            "length(trim(code)) > 0 AND length(trim(name)) > 0",
            name="ck_ledger_accounts_non_blank",
        ),
    )

    def __repr__(self) -> str:
        return f"<LedgerAccount code={self.code} type={self.account_type}>"