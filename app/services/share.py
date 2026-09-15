"""Share service."""

import uuid

from sqlalchemy.orm import Session

from app.models.share import Share
from app.models.user import User
from app.repositories.share import ShareRepository
from app.services.access import (
    authorize_chama_access,
    get_chama_or_404,
    get_target_membership,
)


class ShareService:
    def __init__(self, db: Session):
        self.db = db
        self.shares = ShareRepository(db)

    def list_for_membership(
        self, *, actor: User, chama_id: uuid.UUID, membership_id: uuid.UUID
    ) -> list[Share]:
        chama = get_chama_or_404(self.db, chama_id)
        authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        membership = get_target_membership(self.db, chama_id=chama.id, membership_id=membership_id)
        return self.shares.list_by_membership(membership.id)