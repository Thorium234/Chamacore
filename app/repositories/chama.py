"""Chama repository."""

import uuid

from app.models.chama import Chama
from app.repositories.base import BaseRepository


class ChamaRepository(BaseRepository):
    def get_by_id(self, chama_id: uuid.UUID) -> Chama | None:
        return self.db.get(Chama, chama_id)

    def create(
        self,
        *,
        name: str,
        description: str | None,
        registration_fee_amount,
        status,
        created_by_user_id: uuid.UUID,
    ) -> Chama:
        chama = Chama(
            name=name,
            description=description,
            registration_fee_amount=registration_fee_amount,
            status=status,
            created_by_user_id=created_by_user_id,
        )
        self.db.add(chama)
        self.db.flush()
        return chama