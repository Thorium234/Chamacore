"""Shared financial helpers used by the loan and payout services.

These helpers derive figures from authoritative records on demand:
- Cash availability comes from the ledger (never a stored balance).
- Share value comes from ACTIVE share rows (confirmed contributions).
"""

import uuid
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import StateError
from app.models.enums import ShareStatus
from app.models.ledger_account import LedgerAccount
from app.models.ledger_entry import LedgerEntry
from app.models.share import Share


def get_account_id(db: Session, chama_id: uuid.UUID, code: str) -> uuid.UUID:
    account = db.scalars(
        select(LedgerAccount).where(
            LedgerAccount.chama_id == chama_id, LedgerAccount.code == code
        )
    ).first()
    if account is None:
        raise StateError(f"The default ledger account {code} is missing for this Chama")
    return account.id


def available_chama_cash(db: Session, chama_id: uuid.UUID) -> Decimal:
    """Return the ledger Cash balance for the Chama (debits minus credits).

    Cash is an ASSET account, so a positive value is cash held. The balance
    is always computed from posted ledger entries; nothing is stored.
    """
    cash_account_id = get_account_id(db, chama_id, "1000")
    balance = db.scalars(
        select(
            func.coalesce(func.sum(LedgerEntry.debit), Decimal("0"))
            - func.coalesce(func.sum(LedgerEntry.credit), Decimal("0"))
        ).where(
            LedgerEntry.chama_id == chama_id,
            LedgerEntry.account_id == cash_account_id,
        )
    ).one()
    return Decimal(balance).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def member_share_value(db: Session, membership_id: uuid.UUID) -> Decimal:
    """Member share value = ACTIVE share units times the unit price.

    Derived on demand from confirmed contribution share records.
    """
    units = db.scalars(
        select(
            func.coalesce(func.sum(Share.units), Decimal("0")).label("units")
        ).where(
            Share.membership_id == membership_id,
            Share.status == ShareStatus.ACTIVE,
        )
    ).one()
    unit_price = get_settings().share_unit_price
    return (Decimal(units) * unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)