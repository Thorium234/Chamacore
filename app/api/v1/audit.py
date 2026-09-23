"""Audit event endpoints (ADR-023)."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.audit import AuditEventOut
from app.services.audit import AuditService

router = APIRouter(tags=["audit"])


@router.get("/chamas/{chama_id}/audit-events", response_model=list[AuditEventOut])
def list_audit_events(
    chama_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    events = AuditService(db).list_for_chama(actor=actor, chama_id=chama_id)
    return [AuditEventOut.model_validate(e) for e in events]