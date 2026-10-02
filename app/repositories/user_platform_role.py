"""Platform-role repository: cross-Chama administration grants."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import RoleName
from app.models.user_platform_role import UserPlatformRole


class UserPlatformRoleRepository:
    def __init__(self, db: Session):
        self.db = db

    def has_role(self, *, user_id: uuid.UUID, role: RoleName) -> bool:
        stmt = select(UserPlatformRole.id).where(
            UserPlatformRole.user_id == user_id,
            UserPlatformRole.role == role,
        )
        return self.db.scalars(stmt).first() is not None

    def list_for_user(self, *, user_id: uuid.UUID) -> list[UserPlatformRole]:
        stmt = select(UserPlatformRole).where(UserPlatformRole.user_id == user_id)
        return list(self.db.scalars(stmt))

    def list_admin_user_ids(self, *, role: RoleName = RoleName.PLATFORM_ADMIN) -> list[uuid.UUID]:
        stmt = select(UserPlatformRole.user_id).where(UserPlatformRole.role == role)
        return list(self.db.scalars(stmt))

    def grant(
        self,
        *,
        user_id: uuid.UUID,
        role: RoleName,
        granted_by_user_id: uuid.UUID | None,
        granted_at: datetime,
    ) -> UserPlatformRole:
        assignment = UserPlatformRole(
            user_id=user_id,
            role=role,
            granted_by_user_id=granted_by_user_id,
            granted_at=granted_at,
        )
        self.db.add(assignment)
        self.db.flush()
        return assignment

    def get(self, *, user_id: uuid.UUID, role: RoleName) -> UserPlatformRole | None:
        stmt = select(UserPlatformRole).where(
            UserPlatformRole.user_id == user_id,
            UserPlatformRole.role == role,
        )
        return self.db.scalars(stmt).first()