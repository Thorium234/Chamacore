"""Ledger repository."""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.ledger_account import LedgerAccount
from app.models.ledger_entry import LedgerEntry
from app.models.ledger_transaction import LedgerTransaction
from app.repositories.base import BaseRepository


class LedgerAccountRepository(BaseRepository):
    def get_in_chama(self, chama_id: uuid.UUID, account_id: uuid.UUID) -> LedgerAccount | None:
        return self.db.scalars(
            select(LedgerAccount).where(
                LedgerAccount.id == account_id, LedgerAccount.chama_id == chama_id
            )
        ).first()


class LedgerRepository(BaseRepository):
    def get_by_source(self, source_type: str, source_id: uuid.UUID) -> LedgerTransaction | None:
        return self.db.scalars(
            select(LedgerTransaction).where(
                LedgerTransaction.source_type == source_type,
                LedgerTransaction.source_id == source_id,
            )
        ).first()

    def get_by_id_in_chama(
        self, chama_id: uuid.UUID, transaction_id: uuid.UUID
    ) -> LedgerTransaction | None:
        return self.db.scalars(
            select(LedgerTransaction)
            .options(selectinload(LedgerTransaction.entries))
            .where(
                LedgerTransaction.id == transaction_id,
                LedgerTransaction.chama_id == chama_id,
            )
        ).first()

    def get_reversal_for(self, transaction_id: uuid.UUID) -> LedgerTransaction | None:
        return self.db.scalars(
            select(LedgerTransaction).where(
                LedgerTransaction.reverses_transaction_id == transaction_id
            )
        ).first()

    def list_by_chama(self, chama_id: uuid.UUID) -> list[LedgerTransaction]:
        stmt = (
            select(LedgerTransaction)
            .options(selectinload(LedgerTransaction.entries))
            .where(LedgerTransaction.chama_id == chama_id)
            .order_by(LedgerTransaction.created_at, LedgerTransaction.id)
        )
        return list(self.db.scalars(stmt))

    def create_transaction(
        self,
        *,
        chama_id: uuid.UUID,
        source_type: str,
        source_id: uuid.UUID,
        description: str | None,
        posted_by_user_id: uuid.UUID,
        reverses_transaction_id: uuid.UUID | None,
        entries: list[tuple[uuid.UUID, Decimal, Decimal]],
    ) -> LedgerTransaction:
        transaction = LedgerTransaction(
            chama_id=chama_id,
            source_type=source_type,
            source_id=source_id,
            description=description,
            posted_by_user_id=posted_by_user_id,
            reverses_transaction_id=reverses_transaction_id,
        )
        self.db.add(transaction)
        self.db.flush()
        for account_id, debit, credit in entries:
            self.db.add(
                LedgerEntry(
                    transaction_id=transaction.id,
                    account_id=account_id,
                    debit=debit,
                    credit=credit,
                )
            )
        self.db.flush()
        return transaction