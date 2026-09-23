"""Registration fee payment repository."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import RegistrationFeePaymentStatus
from app.models.registration_fee_payment import RegistrationFeePayment
from app.repositories.base import BaseRepository


class RegistrationFeePaymentRepository(BaseRepository):
    def get_by_id(self, payment_id: uuid.UUID) -> RegistrationFeePayment | None:
        return self.db.get(RegistrationFeePayment, payment_id)

    def confirmed_by_fee(self, fee_id: uuid.UUID) -> RegistrationFeePayment | None:
        return self.db.scalars(
            select(RegistrationFeePayment).where(
                RegistrationFeePayment.fee_id == fee_id,
                RegistrationFeePayment.status == RegistrationFeePaymentStatus.CONFIRMED,
            )
        ).first()

    def list_by_fee(self, fee_id: uuid.UUID) -> list[RegistrationFeePayment]:
        stmt = (
            select(RegistrationFeePayment)
            .where(RegistrationFeePayment.fee_id == fee_id)
            .order_by(RegistrationFeePayment.paid_at, RegistrationFeePayment.id)
        )
        return list(self.db.scalars(stmt))

    def create(
        self,
        *,
        chama_id: uuid.UUID,
        fee_id: uuid.UUID,
        membership_id: uuid.UUID,
        amount,
        recorded_by_user_id: uuid.UUID,
        note: str | None,
    ) -> RegistrationFeePayment:
        payment = RegistrationFeePayment(
            chama_id=chama_id,
            fee_id=fee_id,
            membership_id=membership_id,
            amount=amount,
            recorded_by_user_id=recorded_by_user_id,
            note=note,
        )
        self.db.add(payment)
        self.db.flush()
        return payment