"""PaymentConnection model: a Chama-scoped gateway credential record (ADR-017)."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import PaymentConnectionStatus, PaymentEnvironment, PaymentProviderCode

if TYPE_CHECKING:
    from app.models.chama import Chama
    from app.models.user import User


class PaymentConnection(Base, UUIDMixin, TimestampMixin):
    """One Chama-provider-environment credential record.

    ``encrypted_credentials`` is the AES-GCM sealed envelope of the provider
    credential map (ADR-017). It must never appear in response schemas,
    logs, repr output, or OpenAPI examples.
    """

    __tablename__ = "payment_connections"

    chama_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chamas.id", ondelete="RESTRICT"), nullable=False
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
    status: Mapped[PaymentConnectionStatus] = mapped_column(
        Enum(
            PaymentConnectionStatus,
            native_enum=False,
            length=30,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=PaymentConnectionStatus.PENDING_VALIDATION,
    )
    encrypted_credentials: Mapped[str] = mapped_column(Text, nullable=False)
    encryption_key_version: Mapped[int] = mapped_column(nullable=False, default=1)
    credential_version: Mapped[int] = mapped_column(nullable=False, default=1)
    masked_account_identifier: Mapped[str] = mapped_column(String(120), nullable=False)
    last_validated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_validation_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    chama: Mapped["Chama"] = relationship()
    created_by: Mapped["User"] = relationship(foreign_keys=[created_by_user_id])
    updated_by: Mapped["User"] = relationship(foreign_keys=[updated_by_user_id])

    __table_args__ = (
        UniqueConstraint(
            "chama_id", "provider_code", "environment",
            name="uq_payment_connections_chama_provider_environment",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<PaymentConnection provider={self.provider_code.value} "
            f"environment={self.environment.value} status={self.status.value}>"
        )