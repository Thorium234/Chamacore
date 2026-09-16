"""Ledger endpoints (financial transaction history)."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.ledger import LedgerEntryOut, LedgerTransactionOut
from app.services.ledger import LedgerService

router = APIRouter(tags=["ledger"])


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


@router.get("/chamas/{chama_id}/ledger", response_model=list[LedgerTransactionOut])
def list_ledger(
    chama_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    transactions = LedgerService(db).list_by_chama(actor=actor, chama_id=chama_id)
    return [_to_out(t) for t in transactions]