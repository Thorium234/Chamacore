"""User repository."""

import uuid

from sqlalchemy import or_, select

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        if not email:
            return None
        stmt = select(User).where(User.email == email.lower())
        return self.db.scalars(stmt).first()

    def get_by_phone(self, phone: str) -> User | None:
        if not phone:
            return None
        from app.models.member import Member

        stmt = (
            select(User)
            .join(Member, User.member_id == Member.id)
            .where(Member.phone_number == phone)
        )
        return self.db.scalars(stmt).first()

    def get_by_government_id(self, government_id: str) -> User | None:
        if not government_id:
            return None
        from app.models.member import Member

        stmt = (
            select(User)
            .join(Member, User.member_id == Member.id)
            .where(Member.government_id == government_id)
        )
        return self.db.scalars(stmt).first()

    def get_by_member_id(self, member_id: uuid.UUID) -> User | None:
        stmt = select(User).where(User.member_id == member_id)
        return self.db.scalars(stmt).first()

    def search(self, query: str, *, limit: int, offset: int) -> list[User]:
        from app.models.member import Member

        pattern = f"%{query.strip()}%"
        stmt = (
            select(User)
            .outerjoin(Member, User.member_id == Member.id)
            .where(
                or_(
                    User.email.ilike(pattern),
                    Member.phone_number.ilike(pattern),
                    Member.government_id.ilike(pattern),
                )
            )
            .order_by(User.created_at.desc(), User.id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt))

    def create(self, email: str, password_hash: str) -> User:
        user = User(email=email.lower(), password_hash=password_hash)
        self.db.add(user)
        self.db.flush()
        return user
