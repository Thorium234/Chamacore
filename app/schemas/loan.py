"""Pydantic schemas for loans and loan repayments (ADR-020)."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Money, PositiveMoney


class LoanApplyRequest(BaseModel):
    principal: PositiveMoney
    term_months: int = Field(ge=3, le=12)
    note: str | None = Field(default=None, max_length=1000)


class LoanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chama_id: uuid.UUID
    membership_id: uuid.UUID
    principal: Money
    interest_rate: Decimal
    term_months: int
    total_interest: Money
    total_expected_repayment: Money
    outstanding_principal: Money
    outstanding_interest: Money
    status: str
    is_overdue: bool
    application_date: datetime
    approval_date: datetime | None
    disbursement_date: datetime | None
    maturity_date: datetime | None
    approved_by_user_id: uuid.UUID | None
    disbursed_by_user_id: uuid.UUID | None
    recorded_by_user_id: uuid.UUID
    note: str | None
    created_at: datetime
    updated_at: datetime


class LoanRepaymentCreate(BaseModel):
    amount: PositiveMoney
    note: str | None = Field(default=None, max_length=1000)


class LoanRepaymentReverseRequest(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class LoanRejectRequest(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class LoanRepaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    loan_id: uuid.UUID
    amount: Money
    principal_portion: Money
    interest_portion: Money
    status: str
    recorded_by_user_id: uuid.UUID
    recorded_at: datetime
    note: str | None
    created_at: datetime
    updated_at: datetime