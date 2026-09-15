"""Role repository."""

from sqlalchemy import select

from app.models.enums import RoleName
from app.models.role import Role
from app.repositories.base import BaseRepository


class RoleRepository(BaseRepository):
    def get_by_name(self, name: RoleName) -> Role | None:
        stmt = select(Role).where(Role.name == name.value)
        return self.db.scalars(stmt).first()

    def list_all(self) -> list[Role]:
        stmt = select(Role).order_by(Role.name)
        return list(self.db.scalars(stmt))