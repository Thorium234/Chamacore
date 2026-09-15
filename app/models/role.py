"""Role model. Seeded once by migration."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin
from app.models.enums import RoleName

if TYPE_CHECKING:
    from app.models.membership import Membership


class Role(Base, UUIDMixin):
    __tablename__ = "roles"

    name: Mapped[RoleName] = mapped_column(String(30), unique=True, nullable=False)

    def __repr__(self) -> str:
        return f"<Role name={self.name}>"