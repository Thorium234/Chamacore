"""Pydantic schemas for registration fee payments (ADR-022)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.common import Money


class RegistrationFeePaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    fee_id: uuid.UUID
    amount: Money
    status: str
    recorded_by_user_id: uuid.UUID
    paid_at: datetime
    note: str | None
    created_at: datetime
    updated_at: datetime