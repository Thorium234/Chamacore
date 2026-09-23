"""Pydantic schemas for payouts (ADR-021)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Money, PositiveMoney


class PayoutRequestCreate(BaseModel):
    amount: PositiveMoney
    note: str | None = Field(default=None, max_length=1000)


class PayoutOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chama_id: uuid.UUID
    membership_id: uuid.UUID
    amount: Money
    status: str
    requested_by_user_id: uuid.UUID
    approved_by_user_id: uuid.UUID | None
    processed_by_user_id: uuid.UUID | None
    completed_by_user_id: uuid.UUID | None
    failure_reason: str | None
    requested_at: datetime
    approved_at: datetime | None
    processed_at: datetime | None
    completed_at: datetime | None
    note: str | None
    created_at: datetime
    updated_at: datetime


class PayoutFailRequest(BaseModel):
    failure_reason: str = Field(min_length=1, max_length=500)