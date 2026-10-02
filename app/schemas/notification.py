"""Pydantic schemas for in-app notifications."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import NotificationChannel


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: str
    title: str
    body: str | None
    channel: NotificationChannel
    chama_id: uuid.UUID | None
    resource_type: str | None
    resource_id: uuid.UUID | None
    actor_user_id: uuid.UUID | None
    payload: dict | None
    is_read: bool
    read_at: datetime | None
    created_at: datetime


class UnreadCountOut(BaseModel):
    unread_count: int


class MarkAllReadOut(BaseModel):
    updated: int