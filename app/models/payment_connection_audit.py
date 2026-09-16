"""Audit trail for the payment-connection credential lifecycle (ADR-017)."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin
from app.models.enums import (
    PaymentConnectionAuditAction,
    PaymentConnectionStatus,
)

if TYPE_CHECKING:
    from app.models.payment_connection import PaymentConnection
    from app.models.user import User


class PaymentConnectionAudit(Base, UUIDMixin):
    """Who performed which credential-lifecycle action, without the secret."""

    __tablename__ = "payment_connection_audit"

    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payment_connections.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[PaymentConnectionAuditAction] = mapped_column(
        Enum(
            PaymentConnectionAuditAction,
            native_enum=False,
            length=30,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    previous_status: Mapped[PaymentConnectionStatus | None] = mapped_column(
        Enum(
            PaymentConnectionStatus,
            native_enum=False,
            length=30,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=True,
    )
    new_status: Mapped[PaymentConnectionStatus | None] = mapped_column(
        Enum(
            PaymentConnectionStatus,
            native_enum=False,
            length=30,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=True,
    )
    credential_version: Mapped[int | None] = mapped_column(nullable=True)

    connection: Mapped["PaymentConnection"] = relationship()
    actor: Mapped["User"] = relationship()