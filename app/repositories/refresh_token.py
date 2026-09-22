"""Refresh token repository."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.refresh_token import RefreshToken
from app.repositories.base import BaseRepository


class RefreshTokenRepository(BaseRepository):
    def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        return self.db.scalars(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        ).first()

    def create(
        self, *, user_id: uuid.UUID, token_hash: str, expires_at: datetime
    ) -> RefreshToken:
        token = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self.db.add(token)
        self.db.flush()
        return token

    def revoke(self, token: RefreshToken, *, revoked_at: datetime) -> None:
        token.revoked_at = revoked_at
        self.db.flush()