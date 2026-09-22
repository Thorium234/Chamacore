"""Ledger endpoints (financial transaction history, account balances)."""

import base64
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.ledger import (
    LedgerAccountEntriesOut,
    LedgerAccountOut,
    LedgerAccountsOut,
    LedgerEntryOut,
    LedgerEntryRowOut,
    LedgerHistoryOut,
    LedgerTransactionOut,
)
from app.services.ledger import LedgerService

router = APIRouter(tags=["ledger"])


def _encode_cursor(created_at: datetime, row_id: uuid.UUID) -> str:
    payload = json.dumps({"t": created_at.isoformat(), "i": str(row_id)})
    return base64.urlsafe_b64encode(payload.encode("ascii")).decode("ascii")


def _decode_cursor(cursor: str | None) -> tuple[datetime | None, uuid.UUID | None]:
    if not cursor:
        return None, None
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")))
        created_at = datetime.fromisoformat(payload["t"])
        row_id = uuid.UUID(payload["i"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=422, detail="Invalid ledger cursor") from exc
    return created_at, row_id


def _to_out(transaction) -> LedgerTransactionOut:
    return LedgerTransactionOut(
        id=transaction.id,
        chama_id=transaction.chama_id,
        source_type=transaction.source_type,
        source_id=transaction.source_id,
        description=transaction.description,
        posted_by_user_id=transaction.posted_by_user_id,
        reverses_transaction_id=transaction.reverses_transaction_id,
        created_at=transaction.created_at,
        entries=[
            LedgerEntryOut(
                account_id=entry.account_id,
                account_code=entry.account.code,
                account_name=entry.account.name,
                debit=entry.debit,
                credit=entry.credit,
            )
            for entry in transaction.entries
        ],
    )


@router.get("/chamas/{chama_id}/ledger", response_model=LedgerHistoryOut)
def list_ledger(
    chama_id: uuid.UUID,
    limit: int = Query(default=25, ge=1, le=100),
    cursor: str | None = Query(default=None),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    service = LedgerService(db)
    before_created_at, before_id = _decode_cursor(cursor)
    page = service.list_page(
        actor=actor,
        chama_id=chama_id,
        limit=limit + 1,
        before_created_at=before_created_at,
        before_id=before_id,
    )
    has_more = len(page) > limit
    items = page[:limit]
    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = _encode_cursor(last.created_at, last.id)
    return LedgerHistoryOut(
        items=[_to_out(t) for t in items], next_cursor=next_cursor, has_more=has_more
    )


def _account_to_out(account, balance) -> LedgerAccountOut:
    return LedgerAccountOut(
        id=account.id,
        code=account.code,
        name=account.name,
        account_type=account.account_type.value,
        description=account.description,
        balance=balance,
    )


@router.get("/chamas/{chama_id}/ledger/accounts", response_model=LedgerAccountsOut)
def list_account_balances(
    chama_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    service = LedgerService(db)
    pairs = service.list_accounts(actor=actor, chama_id=chama_id)
    return LedgerAccountsOut(
        items=[_account_to_out(account, balance) for account, balance in pairs]
    )


@router.get(
    "/chamas/{chama_id}/ledger/accounts/{account_id}/entries",
    response_model=LedgerAccountEntriesOut,
)
def list_account_entries(
    chama_id: uuid.UUID,
    account_id: uuid.UUID,
    limit: int = Query(default=25, ge=1, le=100),
    cursor: str | None = Query(default=None),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    service = LedgerService(db)
    before_created_at, before_id = _decode_cursor(cursor)
    page = service.list_account_entries_page(
        actor=actor,
        chama_id=chama_id,
        account_id=account_id,
        limit=limit + 1,
        before_created_at=before_created_at,
        before_id=before_id,
    )
    has_more = len(page) > limit
    items = page[:limit]
    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = _encode_cursor(last.created_at, last.id)

    account = None
    balance = None
    for acc, bal in service.list_accounts(actor=actor, chama_id=chama_id):
        if acc.id == account_id:
            account, balance = acc, bal
            break
    if account is None:
        raise HTTPException(status_code=404, detail="Ledger account not found in this Chama")

    return LedgerAccountEntriesOut(
        account=_account_to_out(account, balance),
        items=[
            LedgerEntryRowOut(
                id=entry.id,
                transaction_id=entry.transaction_id,
                source_type=entry.transaction.source_type,
                source_id=entry.transaction.source_id,
                description=entry.transaction.description,
                debit=entry.debit,
                credit=entry.credit,
                created_at=entry.created_at,
            )
            for entry in items
        ],
        next_cursor=next_cursor,
        has_more=has_more,
    )