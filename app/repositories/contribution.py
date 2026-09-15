"""Contribution repository."""

import uuid
from decimal import Decimal

from app.models.contribution import Contribution
from app.models.enums import ContributionStatus
from app.repositories.base import BaseRepository


class ContributionRepository(BaseRepository):
    def get_by_id(self, contribution_id: uuid.UUID) -> Contribution | None:
        return self.db.get(Contribution, contribution_id)

    def list_by_chama(self, chama_id: uuid.UUID) -> list[Contribution]:
        from sqlalchemy import select

        stmt = (
            select(Contribution)
            .join(Contribution.membership)
            .where(Contribution.membership.has(chama_id=chama_id))
            .order_by(Contribution.period, Contribution.created_at)
        )
        return list(self.db.scalars(stmt))

    def create(
        self,
        *,
        membership_id: uuid.UUID,
        amount: Decimal,
        period: str,
        recorded_by_user_id: uuid.UUID,
        note: str | None,
    ) -> Contribution:
        contribution = Contribution(
            membership_id=membership_id,
            amount=amount,
            period=period,
            status=ContributionStatus.PENDING,
            recorded_by_user_id=recorded_by_user_id,
            note=note,
        )
        self.db.add(contribution)
        self.db.flush()
        return contribution