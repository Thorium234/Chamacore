"""Chama service."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.errors import ConflictError, StateError
from app.models.chama import Chama
from app.models.enums import ChamaStatus, MembershipStatus, RoleName
from app.models.membership import Membership
from app.models.user import User
from app.repositories.chama import ChamaRepository
from app.repositories.member import MemberRepository
from app.repositories.membership import MembershipRepository
from app.repositories.registration_fee import RegistrationFeeRepository
from app.repositories.role import RoleRepository
from app.schemas.chama import ChamaCreate, ChamaUpdate, MemberDetails
from app.services.access import authorize_chama_access, get_chama_or_404, require_role
from app.services.audit import AuditAction, AuditService
from app.services.ledger import LedgerService


class ChamaService:
    def __init__(self, db: Session):
        self.db = db
        self.chamas = ChamaRepository(db)
        self.members = MemberRepository(db)
        self.memberships = MembershipRepository(db)
        self.roles = RoleRepository(db)
        self.fees = RegistrationFeeRepository(db)
        self.ledger = LedgerService(db)
        self.audit = AuditService(db)

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
        self.ledger.seed_default_chart_of_accounts(chama.id)
        self.db.commit()
        self.audit.record_commit(
            actor=user,
            chama_id=chama.id,
            action=AuditAction.CHAMA_CREATE,
            resource_type="chama",
            resource_id=chama.id,
            payload={"name": chama.name},
        )
        return chama

    def get_chama(self, *, actor: User, chama_id: uuid.UUID) -> Chama:
        chama = get_chama_or_404(self.db, chama_id)
        authorize_chama_access(self.db, actor=actor, chama_id=chama_id)
        return chama

    def list_my_chamas(self, *, actor: User) -> list[Chama]:
        """Return Chamas where the actor holds an ACTIVE membership."""
        if actor.member_id is None:
            return []
        stmt = (
            select(Chama)
            .join(Membership, Membership.chama_id == Chama.id)
            .where(
                Membership.member_id == actor.member_id,
                Membership.status == MembershipStatus.ACTIVE,
            )
            .order_by(Chama.created_at.desc(), Chama.id)
        )
        return list(self.db.scalars(stmt))

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
        self.audit.record_commit(
            actor=actor,
            chama_id=chama.id,
            action=AuditAction.CHAMA_UPDATE,
            resource_type="chama",
            resource_id=chama.id,
            payload={
                "name": data.name,
                "description": data.description,
                "registration_fee_amount": str(data.registration_fee_amount)
                if data.registration_fee_amount is not None
                else None,
            },
        )
        if data.status is not None:
            self.audit.record_commit(
                actor=actor,
                chama_id=chama.id,
                action=AuditAction.CHAMA_STATUS_CHANGE,
                resource_type="chama",
                resource_id=chama.id,
                payload={"status": chama.status.value},
            )
        return chama

    def _resolve_creator_member(self, user: User, data: ChamaCreate):
        """Attach the creator to their linked member when one exists (ADR-008).

        A user whose `member_id` is already set keeps using that member for
        every Chama they create, so they are always an ACTIVE member of the new
        Chama. The request body's `member` details are ignored for linked users
        because `users.member_id` is the authoritative identity; the payload is
        only used to create a member when the user is not yet linked.
        """
        if user.member_id is not None:
            member = self.members.get_by_id(user.member_id)
            if member is None:
                raise StateError("The linked member no longer exists")
            return member
        if data.member is not None:
            return self._create_member(data.member)
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