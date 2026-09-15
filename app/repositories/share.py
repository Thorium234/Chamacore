"""Share repository."""

import uuid
from decimal import Decimal

from app.models.enums import ShareStatus
from app.models.share import Share
from app.repositories.base import BaseRepository


class ShareRepository(BaseRepository):
    def get_by_id(self, share_id: uuid.UUID) -> Share | None:
        return self.db.get(Share, share_id)

    def list_by_membership(self, membership_id: uuid.UUID) -> list[Share]:
        from sqlalchemy import select

        stmt = (
            select(Share)
            .where(Share.membership_id == membership_id)
            .order_by(Share.created_at)
        )
        return list(self.db.scalars(stmt))

    def create(
        self,
        *,
        membership_id: uuid.UUID,
        contribution_id: uuid.UUID,
        units: Decimal,
    ) -> Share:
        share = Share(
            membership_id=membership_id,
            contribution_id=contribution_id,
            units=units,
            status=ShareStatus.ACTIVE,
        )
        self.db.add(share)
        self.db.flush()
        return share