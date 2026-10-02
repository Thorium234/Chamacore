"""Pydantic schemas for platform administration."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ChamaStatus, RoleName


class PlatformChamaOut(BaseModel):
    """Platform-wide Chama view. Visible only to PLATFORM_ADMIN holders."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    status: ChamaStatus
    registration_fee_amount: Decimal
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    active_member_count: int = 0
    membership_count: int = 0


class PlatformChamaStatusUpdate(BaseModel):
    status: ChamaStatus = Field(
        description=(
            "Target lifecycle state. DISSOLVED is terminal and cannot be left."
        )
    )
    reason: str | None = Field(default=None, max_length=500)


class PlatformUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    is_active: bool
    must_change_password: bool
    member_id: uuid.UUID | None
    platform_roles: list[RoleName] = []
    created_at: datetime


class PlatformStatsOut(BaseModel):
    total_chamas: int
    active_chamas: int
    pending_chamas: int
    suspended_chamas: int
    dissolved_chamas: int
    total_users: int
    total_members: int
    platform_admins: int