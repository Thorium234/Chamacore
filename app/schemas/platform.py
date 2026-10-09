"""Pydantic schemas for platform administration."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import ChamaStatus, RoleName


class PlatformChamaOut(BaseModel):
    """Platform-wide Chama view. Visible only to PLATFORM_ADMIN holders."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    status: ChamaStatus
    created_by_user_id: uuid.UUID
    owner_name: str | None
    owner_email: EmailStr
    owner_phone: str | None
    membership_count: int
    active_member_count: int
    created_at: datetime
    updated_at: datetime


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
    member_name: str | None = None
    member_phone: str | None = None
    platform_roles: list[RoleName] = []
    created_at: datetime


class PlatformAdminGrantRequest(BaseModel):
    email: EmailStr


class PlatformStatsOut(BaseModel):
    total_chamas: int
    active_chamas: int
    pending_chamas: int
    suspended_chamas: int
    dissolved_chamas: int
    total_users: int
    total_members: int
    platform_admins: int
