"""ProviderTransaction model: provider identifiers and normalized status (ADR-016).

History is preserved through ``payment_events`` (the immutable callback log);
this row is the current normalized provider view for a payment attempt.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import ProviderTransactionStatus

if TYPE_CHECKING:
    from app.models.payment_attempt import PaymentAttempt
    from app.models.payment_connection import PaymentConnection


class ProviderTransaction(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "provider_transactions"

    payment_attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payment_attempts.id", ondelete="RESTRICT"), nullable=False
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payment_connections.id", ondelete="RESTRICT"), nullable=False
    )
    provider_request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    normalized_status: Mapped[ProviderTransactionStatus] = mapped_column(
        Enum(
            ProviderTransactionStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=ProviderTransactionStatus.PENDING,
    )
    raw_status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_queried_at: Mapped[datetime | None] = mapped_column(nullable=True)

    payment_attempt: Mapped["PaymentAttempt"] = relationship()
    connection: Mapped["PaymentConnection"] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "payment_attempt_id", name="uq_provider_transactions_attempt"
        ),
        Index(
            "uq_provider_transactions_request_id",
            "provider_request_id",
            unique=True,
            sqlite_where=text("provider_request_id IS NOT NULL"),
            postgresql_where=text("provider_request_id IS NOT NULL"),
        ),
        Index(
            "uq_provider_transactions_txn_id",
            "provider_transaction_id",
            unique=True,
            sqlite_where=text("provider_transaction_id IS NOT NULL"),
            postgresql_where=text("provider_transaction_id IS NOT NULL"),
        ),
    )

    def __repr__(self) -> str:
        return f"<ProviderTransaction normalized_status={self.normalized_status.value}>"