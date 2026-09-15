"""Pydantic schemas for members and chamas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ChamaStatus
from app.schemas.common import Money


class MemberDetails(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone_number: str = Field(min_length=3, max_length=20)
    government_id: str = Field(min_length=1, max_length=50)


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    first_name: str
    last_name: str
    phone_number: str
    government_id: str
    created_at: datetime


class MemberPublic(BaseModel):
    """Public view used in membership listings — government ID omitted (ADR decision)."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    first_name: str
    last_name: str
    phone_number: str
    created_at: datetime


class ChamaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    registration_fee_amount: Money
    status: str
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ChamaCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    registration_fee_amount: Money = Decimal("0")
    member: MemberDetails | None = None


class ChamaUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    registration_fee_amount: Money | None = None
    status: ChamaStatus | None = None