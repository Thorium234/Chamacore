"""Pydantic schemas for the V2 financial ledger."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.schemas.common import Money, SignedMoney


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


class LedgerHistoryOut(BaseModel):
    items: list[LedgerTransactionOut]
    next_cursor: str | None = None
    has_more: bool = False


class LedgerAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    account_type: str
    description: str | None
    # balance = sum(debit) - sum(credit) over posted entries, signed to
    # preserve account-type meaning (assets positive, equity/revenue negative).
    # Always computed on demand, never stored.
    balance: SignedMoney


class LedgerAccountsOut(BaseModel):
    items: list[LedgerAccountOut]


class LedgerEntryRowOut(BaseModel):
    id: uuid.UUID
    transaction_id: uuid.UUID
    source_type: str
    source_id: uuid.UUID
    description: str | None
    debit: Money
    credit: Money
    created_at: datetime


class LedgerAccountEntriesOut(BaseModel):
    account: LedgerAccountOut
    items: list[LedgerEntryRowOut]
    next_cursor: str | None = None
    has_more: bool = False