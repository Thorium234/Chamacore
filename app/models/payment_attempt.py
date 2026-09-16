"""PaymentAttempt model: each provider attempt, including retries (ADR-016)."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import (
    PaymentAttemptStatus,
    PaymentTransferSource,
)

if TYPE_CHECKING:
    from app.models.payment_connection import PaymentConnection
    from app.models.payment_intent import PaymentIntent


class PaymentAttempt(Base, UUIDMixin, TimestampMixin):
    """One request sent to a provider for a payment intent.

    ``failure_message_safe`` is a redacted description: it never contains
    provider secrets, tokens, or full payloads.
    """

    __tablename__ = "payment_attempts"

    payment_intent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payment_intents.id", ondelete="RESTRICT"), nullable=False
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payment_connections.id", ondelete="RESTRICT"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(nullable=False)
    provider_request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    retryable: Mapped[bool] = mapped_column(default=False, nullable=False)
    status: Mapped[PaymentAttemptStatus] = mapped_column(
        Enum(
            PaymentAttemptStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=PaymentAttemptStatus.INITIATED,
    )
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_message_safe: Mapped[str | None] = mapped_column(String(500), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.now)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_transition_source: Mapped[PaymentTransferSource] = mapped_column(
        Enum(
            PaymentTransferSource,
            native_enum=False,
            length=30,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=PaymentTransferSource.CLIENT,
    )

    payment_intent: Mapped["PaymentIntent"] = relationship()
    connection: Mapped["PaymentConnection"] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "payment_intent_id", "attempt_number",
            name="uq_payment_attempts_intent_number",
        ),
        UniqueConstraint(
            "connection_id", "client_reference",
            name="uq_payment_attempts_connection_reference",
        ),
        CheckConstraint("attempt_number >= 1", name="ck_payment_attempts_number_positive"),
        CheckConstraint(
            "status IN ('SUCCEEDED', 'FAILED') OR completed_at IS NULL",
            name="ck_payment_attempts_completed_only_final",
        ),
    )

    def __repr__(self) -> str:
        return f"<PaymentAttempt #{self.attempt_number} status={self.status.value}>"