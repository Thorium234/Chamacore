"""Chama service."""

import uuid

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.errors import ConflictError, StateError
from app.models.chama import Chama
from app.models.enums import ChamaStatus, RoleName
from app.models.membership import Membership
from app.models.user import User
from app.repositories.chama import ChamaRepository
from app.repositories.member import MemberRepository
from app.repositories.membership import MembershipRepository
from app.repositories.registration_fee import RegistrationFeeRepository
from app.repositories.role import RoleRepository
from app.schemas.chama import ChamaCreate, ChamaUpdate, MemberDetails
from app.services.access import authorize_chama_access, get_chama_or_404, require_role


class ChamaService:
    def __init__(self, db: Session):
        self.db = db
        self.chamas = ChamaRepository(db)
        self.members = MemberRepository(db)
        self.memberships = MembershipRepository(db)
        self.roles = RoleRepository(db)
        self.fees = RegistrationFeeRepository(db)

    def create_chama(self, *, user: User, data: ChamaCreate) -> Chama:
        member = self._resolve_creator_member(user, data)
        if user.member_id is None:
            user.member_id = member.id  # link User to Member (ADR-008)
        chama = self.chamas.create(
            name=data.name,
            description=data.description,
            registration_fee_amount=data.registration_fee_amount,
            status=ChamaStatus.ACTIVE,
            created_by_user_id=user.id,
        )
        creator_membership = self.memberships.create(
            chama_id=chama.id,
            member_id=member.id,
            membership_number=self.memberships.allocate_membership_number(chama.id),
        )
        chairperson = self.roles.get_by_name(RoleName.CHAIRPERSON)
        default_member = self.roles.get_by_name(RoleName.MEMBER)
        self.memberships.add_role(creator_membership.id, chairperson)
        self.memberships.add_role(creator_membership.id, default_member)
        self.fees.create(
            membership_id=creator_membership.id,
            amount=chama.registration_fee_amount,
        )
        self.db.commit()
        return chama

    def get_chama(self, *, actor: User, chama_id: uuid.UUID) -> Chama:
        chama = get_chama_or_404(self.db, chama_id)
        authorize_chama_access(self.db, actor=actor, chama_id=chama_id)
        return chama

    def update_chama(self, *, actor: User, chama_id: uuid.UUID, data: ChamaUpdate) -> Chama:
        chama = get_chama_or_404(self.db, chama_id)
        membership = authorize_chama_access(self.db, actor=actor, chama_id=chama_id)
        require_role(membership, RoleName.CHAIRPERSON)
        if data.name is not None:
            chama.name = data.name
        if data.description is not None:
            chama.description = data.description
        if data.registration_fee_amount is not None:
            chama.registration_fee_amount = data.registration_fee_amount
        if data.status is not None:
            chama.status = data.status
        self.db.commit()
        return chama

    def _resolve_creator_member(self, user: User, data: ChamaCreate):
        if data.member is not None:
            return self._create_member(data.member)
        if user.member_id is not None:
            member = self.members.get_by_id(user.member_id)
            if member is None:
                raise StateError("The linked member no longer exists")
            return member
        raise StateError("member details are required when creating a Chama")

    def _create_member(self, details: MemberDetails):
        if self.members.phone_exists(details.phone_number):
            raise ConflictError("phone_number is already registered to another member")
        if self.members.government_id_exists(details.government_id):
            raise ConflictError("government_id is already registered to another member")
        try:
            return self.members.create(details)
        except IntegrityError:
            self.db.rollback()
            raise ConflictError("A member with these identity details already exists")