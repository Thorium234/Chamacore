"""RegistrationFee repository."""

import uuid
from decimal import Decimal

from app.models.enums import RegistrationFeeStatus
from app.models.registration_fee import RegistrationFee
from app.repositories.base import BaseRepository


class RegistrationFeeRepository(BaseRepository):
    def get_by_membership(self, membership_id: uuid.UUID) -> RegistrationFee | None:
        from sqlalchemy import select

        stmt = select(RegistrationFee).where(RegistrationFee.membership_id == membership_id)
        return self.db.scalars(stmt).first()

    def create(self, *, membership_id: uuid.UUID, amount: Decimal) -> RegistrationFee:
        fee = RegistrationFee(
            membership_id=membership_id,
            amount=amount,
            status=RegistrationFeeStatus.OWED,
        )
        self.db.add(fee)
        self.db.flush()
        return fee