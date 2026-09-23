"""Append-only business audit event model (ADR-023)."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.chama import Chama
    from app.models.user import User


class AuditEvent(Base, UUIDMixin):
    __tablename__ = "audit_events"

    chama_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chamas.id", ondelete="RESTRICT"), nullable=True
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    chama: Mapped["Chama | None"] = relationship()
    actor: Mapped["User | None"] = relationship()

    __table_args__ = (
        Index("ix_audit_events_chama_created", "chama_id", "created_at"),
        Index("ix_audit_events_action", "action"),
        Index("ix_audit_events_resource", "resource_type", "resource_id"),
    )

    def __repr__(self) -> str:
        return f"<AuditEvent action={self.action} success={self.success}>"