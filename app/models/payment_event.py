"""PaymentEvent model: inbound provider callbacks with deduplication (ADR-018)."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin
from app.models.enums import (
    PaymentEnvironment,
    PaymentEventStatus,
    PaymentProviderCode,
)

if TYPE_CHECKING:
    from app.models.payment_connection import PaymentConnection


class PaymentEvent(Base, UUIDMixin):
    """One raw provider callback.

    ``raw_payload`` is retained for reconciliation under the approved
    retention policy (``payment_event_raw_retention_days``) and is never
    returned by any API surface or written to application logs.
    """

    __tablename__ = "payment_events"

    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payment_connections.id", ondelete="RESTRICT"), nullable=False
    )
    provider_code: Mapped[PaymentProviderCode] = mapped_column(
        Enum(
            PaymentProviderCode,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    environment: Mapped[PaymentEnvironment] = mapped_column(
        Enum(
            PaymentEnvironment,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    provider_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[PaymentEventStatus] = mapped_column(
        Enum(
            PaymentEventStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=PaymentEventStatus.RECEIVED,
    )
    received_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.now)
    processed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_transition_source: Mapped[str] = mapped_column(nullable=False, default="PROVIDER_CALLBACK")

    connection: Mapped["PaymentConnection"] = relationship()

    __table_args__ = (
        Index(
            "uq_payment_events_connection_event",
            "connection_id",
            "provider_event_id",
            unique=True,
            sqlite_where=text("provider_event_id IS NOT NULL"),
            postgresql_where=text("provider_event_id IS NOT NULL"),
        ),
        Index("ix_payment_events_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<PaymentEvent provider={self.provider_code.value} status={self.status.value}>"