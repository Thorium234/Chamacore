"""Pydantic schemas for the V3 payment API (ADR-016).

Credential response schemas intentionally never expose secrets or encrypted
blobs: read endpoints return only provider name, environment, status, masked
identifiers, timestamps, and validation state.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    PaymentAttemptStatus,
    PaymentConnectionStatus,
    PaymentEnvironment,
    PaymentEventStatus,
    PaymentIntentStatus,
    PaymentProviderCode,
    PaymentTransferSource,
)
from app.providers.schemas import ProviderCredentials
from app.schemas.common import PositiveMoney


class PaymentConnectionCreate(BaseModel):
    provider_code: PaymentProviderCode
    environment: PaymentEnvironment
    credentials: ProviderCredentials


class PaymentConnectionReplace(BaseModel):
    credentials: ProviderCredentials


class PaymentConnectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chama_id: uuid.UUID
    provider_code: PaymentProviderCode
    environment: PaymentEnvironment
    status: PaymentConnectionStatus
    masked_account_identifier: str
    encryption_key_version: int
    credential_version: int
    last_validated_at: datetime | None
    last_validation_error_code: str | None
    created_by_user_id: uuid.UUID
    updated_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class PaymentIntentCreate(BaseModel):
    membership_id: uuid.UUID
    amount: PositiveMoney
    currency: str = Field(default="KES", pattern=r"^[A-Z]{3}$")
    purpose: str = Field(min_length=1, max_length=255)
    idempotency_key: str = Field(min_length=1, max_length=255)
    contribution_id: uuid.UUID | None = None


class PaymentIntentInitiate(BaseModel):
    connection_id: uuid.UUID


class PaymentIntentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chama_id: uuid.UUID
    membership_id: uuid.UUID
    contribution_id: uuid.UUID | None
    amount: Decimal
    currency: str
    purpose: str
    status: PaymentIntentStatus
    idempotency_key: str
    created_by_user_id: uuid.UUID
    last_transition_source: PaymentTransferSource
    last_transition_by_user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class PaymentAttemptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    payment_intent_id: uuid.UUID
    connection_id: uuid.UUID
    attempt_number: int
    provider_request_id: str | None
    provider_transaction_id: str | None
    client_reference: str
    status: PaymentAttemptStatus
    retryable: bool = False
    failure_code: str | None
    failure_message_safe: str | None
    requested_at: datetime
    completed_at: datetime | None
    last_transition_source: PaymentTransferSource


class PaymentEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    connection_id: uuid.UUID
    provider_code: PaymentProviderCode
    environment: PaymentEnvironment
    provider_event_id: str | None
    status: PaymentEventStatus
    received_at: datetime
    processed_at: datetime | None


class C2BValidationResponse(BaseModel):
    """Safaricom C2B Validation envelope (``ResultCode`` 0 = accept)."""

    ResultCode: int
    ResultDesc: str


class C2BConfirmationResponse(BaseModel):
    """Safaricom C2B Confirmation acknowledgement (any body is ignored)."""

    ok: bool
    event_id: uuid.UUID
    event_status: PaymentEventStatus


class C2BRegisterUrlRequest(BaseModel):
    """Body for activating the Daraja C2B Register-URL step."""

    response_type: Literal["Completed", "Cancelled"] = "Completed"


class C2BRegisterUrlOut(BaseModel):
    """Result of registering C2B Validation/Confirmation URLs with Daraja."""

    accepted: bool
    response_code: str
    response_description: str
    validation_url: str
    confirmation_url: str