"""Loan repository."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.loan import Loan
from app.repositories.base import BaseRepository


class LoanRepository(BaseRepository):
    def get_by_id(self, loan_id: uuid.UUID) -> Loan | None:
        return self.db.scalars(
            select(Loan)
            .options(selectinload(Loan.repayments))
            .where(Loan.id == loan_id)
        ).first()

    def list_by_chama(self, chama_id: uuid.UUID) -> list[Loan]:
        stmt = (
            select(Loan)
            .options(selectinload(Loan.repayments))
            .where(Loan.chama_id == chama_id)
            .order_by(Loan.created_at, Loan.id)
        )
        return list(self.db.scalars(stmt))

    def list_by_membership(self, membership_id: uuid.UUID) -> list[Loan]:
        stmt = (
            select(Loan)
            .options(selectinload(Loan.repayments))
            .where(Loan.membership_id == membership_id)
            .order_by(Loan.created_at, Loan.id)
        )
        return list(self.db.scalars(stmt))