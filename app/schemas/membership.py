"""Pydantic schemas for memberships, roles, registration fees, contributions, and shares."""

import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import MembershipStatus, RoleName
from app.schemas.chama import MemberDetails, MemberPublic
from app.schemas.common import Money, PositiveMoney, Period, Quantity


class MembershipCreate(BaseModel):
    member_id: uuid.UUID | None = None
    member: MemberDetails | None = None

    @model_validator(mode="after")
    def _validate_member_source(self) -> Self:
        if (self.member_id is None) == (self.member is None):
            raise ValueError("provide exactly one of member_id or member details")
        return self


class MembershipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chama_id: uuid.UUID
    member_id: uuid.UUID
    membership_number: int
    status: MembershipStatus
    joined_at: datetime
    member: MemberPublic | None = None
    roles: list[RoleName] = []
    registration_fee: "RegistrationFeeOut | None" = None

    @field_validator("roles", mode="before")
    @classmethod
    def _coerce_role_objects(cls, value):
        if isinstance(value, list):
            return [item.name if hasattr(item, "name") else item for item in value]
        return value


class MembershipStatusUpdate(BaseModel):
    status: MembershipStatus


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: RoleName


class RoleAssignRequest(BaseModel):
    role: RoleName


class RegistrationFeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    membership_id: uuid.UUID
    amount: Money
    status: str
    created_at: datetime
    updated_at: datetime


class ContributionCreate(BaseModel):
    membership_id: uuid.UUID
    amount: PositiveMoney
    period: Period
    note: str | None = Field(default=None, max_length=1000)


class ContributionReverseRequest(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class ContributionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    membership_id: uuid.UUID
    amount: Money
    period: str
    status: str
    recorded_by_user_id: uuid.UUID
    note: str | None
    confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ShareOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    membership_id: uuid.UUID
    contribution_id: uuid.UUID
    units: Quantity
    status: str
    created_at: datetime
    updated_at: datetime


MembershipOut.model_rebuild()