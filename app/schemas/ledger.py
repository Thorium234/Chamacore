"""Pydantic schemas for the V2 financial ledger."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.schemas.common import Money


class LedgerEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account_id: uuid.UUID
    account_code: str
    account_name: str
    debit: Money
    credit: Money


class LedgerTransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chama_id: uuid.UUID
    source_type: str
    source_id: uuid.UUID
    description: str | None
    posted_by_user_id: uuid.UUID
    reverses_transaction_id: uuid.UUID | None
    created_at: datetime
    entries: list[LedgerEntryOut] = []