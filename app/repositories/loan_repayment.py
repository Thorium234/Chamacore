"""Loan repayment repository."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import LoanRepaymentStatus
from app.models.loan_repayment import LoanRepayment
from app.repositories.base import BaseRepository


class LoanRepaymentRepository(BaseRepository):
    def get_by_id(self, repayment_id: uuid.UUID) -> LoanRepayment | None:
        return self.db.get(LoanRepayment, repayment_id)

    def confirmed_by_loan(self, loan_id: uuid.UUID) -> list[LoanRepayment]:
        stmt = (
            select(LoanRepayment)
            .where(
                LoanRepayment.loan_id == loan_id,
                LoanRepayment.status == LoanRepaymentStatus.CONFIRMED,
            )
            .order_by(LoanRepayment.recorded_at, LoanRepayment.id)
        )
        return list(self.db.scalars(stmt))

    def list_by_loan(self, loan_id: uuid.UUID) -> list[LoanRepayment]:
        stmt = (
            select(LoanRepayment)
            .where(LoanRepayment.loan_id == loan_id)
            .order_by(LoanRepayment.recorded_at, LoanRepayment.id)
        )
        return list(self.db.scalars(stmt))

    def create(
        self,
        *,
        chama_id: uuid.UUID,
        loan_id: uuid.UUID,
        amount,
        principal_portion,
        interest_portion,
        recorded_by_user_id: uuid.UUID,
        note: str | None,
    ) -> LoanRepayment:
        repayment = LoanRepayment(
            chama_id=chama_id,
            loan_id=loan_id,
            amount=amount,
            principal_portion=principal_portion,
            interest_portion=interest_portion,
            recorded_by_user_id=recorded_by_user_id,
            note=note,
        )
        self.db.add(repayment)
        self.db.flush()
        return repayment