"""Pydantic schemas for audit events (ADR-023)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chama_id: uuid.UUID | None
    actor_user_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: uuid.UUID | None
    request_id: str | None
    payload: dict | None
    success: bool
    ip_address: str | None
    user_agent: str | None
    created_at: datetime