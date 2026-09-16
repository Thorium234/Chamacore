"""PaymentIntent model: the business-level request to collect money (ADR-016)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import (
    PaymentIntentStatus,
    PaymentTransferSource,
)

if TYPE_CHECKING:
    from app.models.chama import Chama
    from app.models.membership import Membership
    from app.models.user import User


class PaymentIntent(Base, UUIDMixin, TimestampMixin):
    """A Chama's request to collect money from a member via a provider.

    ``contribution_id`` is reserved for the future approved rule that links a
    payment to a contribution (OQ-012/OQ-013). It is always ``NULL`` until a
    decision permits the link and is deliberately not a foreign key.
    """

    __tablename__ = "payment_intents"

    chama_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chamas.id", ondelete="RESTRICT"), nullable=False
    )
    membership_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memberships.id", ondelete="RESTRICT"), nullable=False
    )
    contribution_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KES")
    purpose: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[PaymentIntentStatus] = mapped_column(
        Enum(
            PaymentIntentStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=PaymentIntentStatus.PENDING,
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    idempotency_payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
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
    last_transition_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )

    chama: Mapped["Chama"] = relationship()
    membership: Mapped["Membership"] = relationship()
    created_by: Mapped["User"] = relationship(foreign_keys=[created_by_user_id])

    __table_args__ = (
        UniqueConstraint("chama_id", "idempotency_key", name="uq_payment_intents_chama_key"),
        CheckConstraint("amount > 0", name="ck_payment_intents_amount_positive"),
        CheckConstraint(
            "currency = upper(currency)", name="ck_payment_intents_currency_upper"
        ),
    )

    def __repr__(self) -> str:
        return f"<PaymentIntent amount={self.amount} {self.currency} status={self.status.value}>"