"""Member repository."""

import uuid

from sqlalchemy import select

from app.models.member import Member
from app.repositories.base import BaseRepository
from app.schemas.chama import MemberDetails


class MemberRepository(BaseRepository):
    def get_by_id(self, member_id: uuid.UUID) -> Member | None:
        return self.db.get(Member, member_id)

    def create(self, details: MemberDetails) -> Member:
        member = Member(
            first_name=details.first_name,
            last_name=details.last_name,
            phone_number=details.phone_number,
            government_id=details.government_id,
        )
        self.db.add(member)
        self.db.flush()
        return member

    def phone_exists(self, phone_number: str) -> bool:
        stmt = select(Member.id).where(Member.phone_number == phone_number)
        return self.db.scalars(stmt).first() is not None

    def government_id_exists(self, government_id: str) -> bool:
        stmt = select(Member.id).where(Member.government_id == government_id)
        return self.db.scalars(stmt).first() is not None

    def find_by_identity(self, phone_number: str, government_id: str) -> Member | None:
        stmt = select(Member).where(
            Member.phone_number == phone_number,
            Member.government_id == government_id,
        )
        return self.db.scalars(stmt).first()