"""Strict Pydantic model for the Daraja C2B callback body (ADR-016, C2B).

Safaricom sends a single flat object to both the Validation URL and the
Confirmation URL on every manual Paybill (C2B) payment. The model is strict
on types and ignores unknown fields so a malformed or mutated payload
fails closed in the adapter instead of reaching the service.
"""

from pydantic import BaseModel, ConfigDict, Field


class C2BCallbackBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    TransactionType: str | None = Field(default=None, max_length=32)
    TransID: str | None = Field(default=None, max_length=64)
    TransTime: str | None = Field(default=None, max_length=32)
    TransAmount: str | None = Field(default=None, max_length=32)
    BusinessShortCode: str | None = Field(default=None, max_length=16)
    BillRefNumber: str | None = Field(default=None, max_length=64)
    InvoiceNumber: str | None = Field(default=None, max_length=64)
    OrgAccountBalance: str | None = Field(default=None, max_length=32)
    ThirdPartyTransID: str | None = Field(default=None, max_length=64)
    MSISDN: str | None = Field(default=None, max_length=32)
    FirstName: str | None = Field(default=None, max_length=128)
    MiddleName: str | None = Field(default=None, max_length=128)
    LastName: str | None = Field(default=None, max_length=128)