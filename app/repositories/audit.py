"""Audit event repository (append-only, ADR-023)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent
from app.repositories.base import BaseRepository


class AuditRepository(BaseRepository):
    def create(
        self,
        *,
        chama_id: uuid.UUID | None,
        actor_user_id: uuid.UUID | None,
        action: str,
        resource_type: str,
        resource_id: uuid.UUID | None,
        request_id: str | None,
        payload: dict | None,
        success: bool,
        ip_address: str | None,
        user_agent: str | None,
    ) -> AuditEvent:
        event = AuditEvent(
            chama_id=chama_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=request_id,
            payload=payload,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(event)
        self.db.flush()
        return event

    def list_by_chama(self, chama_id: uuid.UUID, *, limit: int = 200) -> list[AuditEvent]:
        stmt = (
            select(AuditEvent)
            .where(AuditEvent.chama_id == chama_id)
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt))