"""Payout repository."""

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import PayoutStatus
from app.models.payout import Payout
from app.repositories.base import BaseRepository


class PayoutRepository(BaseRepository):
    def get_by_id(self, payout_id: uuid.UUID) -> Payout | None:
        return self.db.get(Payout, payout_id)

    def list_by_chama(self, chama_id: uuid.UUID) -> list[Payout]:
        stmt = (
            select(Payout)
            .where(Payout.chama_id == chama_id)
            .order_by(Payout.requested_at, Payout.id)
        )
        return list(self.db.scalars(stmt))

    def list_by_membership(self, membership_id: uuid.UUID) -> list[Payout]:
        stmt = (
            select(Payout)
            .where(Payout.membership_id == membership_id)
            .order_by(Payout.requested_at, Payout.id)
        )
        return list(self.db.scalars(stmt))

    def completed_total_for_membership(self, membership_id: uuid.UUID) -> Decimal:
        """Sum of COMPLETED (non-reversed) payout amounts for a membership."""
        total = self.db.scalars(
            select(func.coalesce(func.sum(Payout.amount), 0)).where(
                Payout.membership_id == membership_id,
                Payout.status == PayoutStatus.COMPLETED,
            )
        ).one()
        return total