"""Membership and membership-number repository."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.membership import Membership
from app.models.membership_sequence import MembershipSequence
from app.models.role import Role
from app.models.enums import MembershipStatus
from app.repositories.base import BaseRepository


class MembershipRepository(BaseRepository):
    def get_by_id(self, membership_id: uuid.UUID) -> Membership | None:
        return self.db.get(Membership, membership_id)

    def get_by_chama_and_member(
        self, chama_id: uuid.UUID, member_id: uuid.UUID
    ) -> Membership | None:
        stmt = select(Membership).where(
            Membership.chama_id == chama_id, Membership.member_id == member_id
        )
        return self.db.scalars(stmt).first()

    def get_by_number(self, chama_id: uuid.UUID, membership_number: int) -> Membership | None:
        stmt = select(Membership).where(
            Membership.chama_id == chama_id,
            Membership.membership_number == membership_number,
        )
        return self.db.scalars(stmt).first()

    def list_by_chama(self, chama_id: uuid.UUID) -> list[Membership]:
        stmt = (
            select(Membership)
            .where(Membership.chama_id == chama_id)
            .order_by(Membership.membership_number)
        )
        return list(self.db.scalars(stmt))

    def allocate_membership_number(self, chama_id: uuid.UUID) -> int:
        """Allocate the next membership number transactionally (ADR-002, ADR-008).

        Uses SELECT ... FOR UPDATE on the per-Chama sequence row. The
        membership's unique (chama_id, membership_number) constraint is the
        backstop for correctness.
        """
        stmt = (
            select(MembershipSequence)
            .where(MembershipSequence.chama_id == chama_id)
            .with_for_update()
        )
        sequence = self.db.scalars(stmt).first()
        if sequence is None:
            sequence = MembershipSequence(chama_id=chama_id, next_number=1)
            self.db.add(sequence)
            self.db.flush()
            number = 1
            sequence.next_number = 2
            self.db.flush()
            return number
        number = sequence.next_number
        sequence.next_number = number + 1
        self.db.flush()
        return number

    def create(
        self,
        *,
        chama_id: uuid.UUID,
        member_id: uuid.UUID,
        membership_number: int,
        status: MembershipStatus = MembershipStatus.ACTIVE,
    ) -> Membership:
        membership = Membership(
            chama_id=chama_id,
            member_id=member_id,
            membership_number=membership_number,
            status=status,
            joined_at=datetime.now(),
        )
        self.db.add(membership)
        self.db.flush()
        return membership

    def add_role(self, membership_id: uuid.UUID, role: Role) -> None:
        from app.models.membership_role import MembershipRole

        self.db.add(MembershipRole(membership_id=membership_id, role_id=role.id))
        self.db.flush()

    def remove_role(self, membership_id: uuid.UUID, role: Role) -> bool:
        from app.models.membership_role import MembershipRole

        stmt = select(MembershipRole).where(
            MembershipRole.membership_id == membership_id,
            MembershipRole.role_id == role.id,
        )
        link = self.db.scalars(stmt).first()
        if link is None:
            return False
        self.db.delete(link)
        self.db.flush()
        return True