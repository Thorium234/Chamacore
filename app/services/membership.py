"""Membership service."""

import re
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models.enums import MembershipStatus, RoleName
from app.models.membership import Membership
from app.models.user import User
from app.repositories.member import MemberRepository
from app.repositories.membership import MembershipRepository
from app.repositories.registration_fee import RegistrationFeeRepository
from app.repositories.role import RoleRepository
from app.schemas.chama import MemberDetails
from app.schemas.membership import MembershipCreate

from app.services.access import (
    LEADERSHIP_ROLES,
    authorize_chama_access,
    get_chama_or_404,
    get_target_membership,
    require_roles,
)

MAX_NUMBER_RETRIES = 5

_CHAMA_NUMBER_CONSTRAINT = "uq_memberships_chama_number"
_CHAMA_MEMBER_CONSTRAINT = "uq_memberships_chama_member"


def classify_integrity_error(exc: IntegrityError) -> str | None:
    """Return the originating constraint or index name, if identifiable."""
    orig = exc.orig
    if hasattr(orig, "diag"):
        name = getattr(orig.diag, "constraint_name", None)
        if name:
            return name
    text = str(orig)
    if "membership_number" in text:
        return _CHAMA_NUMBER_CONSTRAINT
    if "chama_id" in text and "member_id" in text:
        return _CHAMA_MEMBER_CONSTRAINT
    if "phone_number" in text:
        return "ix_members_phone_number"
    if "government_id" in text:
        return "ix_members_government_id"
    return None


class MembershipService:
    def __init__(self, db: Session):
        self.db = db
        self.members = MemberRepository(db)
        self.memberships = MembershipRepository(db)
        self.roles = RoleRepository(db)
        self.fees = RegistrationFeeRepository(db)

    def list_by_chama(self, *, actor: User, chama_id: uuid.UUID) -> list[Membership]:
        chama = get_chama_or_404(self.db, chama_id)
        authorize_chama_access(self.db, actor=actor, chama_id=chama_id)
        return self.memberships.list_by_chama(chama.id)

    def create_membership(self, *, actor: User, chama_id: uuid.UUID, data: MembershipCreate) -> Membership:
        chama = get_chama_or_404(self.db, chama_id)
        actor_membership = authorize_chama_access(self.db, actor=actor, chama_id=chama_id)
        require_roles(actor_membership, LEADERSHIP_ROLES)

        for attempt in range(MAX_NUMBER_RETRIES):
            try:
                return self._create_membership_once(chama.id, data)
            except IntegrityError as exc:
                constraint = classify_integrity_error(exc)
                self.db.rollback()
                if constraint == _CHAMA_NUMBER_CONSTRAINT and attempt < MAX_NUMBER_RETRIES - 1:
                    continue
                if constraint in (_CHAMA_MEMBER_CONSTRAINT, "ix_members_phone_number", "ix_members_government_id"):
                    raise ConflictError("Duplicate member or membership record")
                raise ConflictError("Could not create membership due to a data conflict") from exc

    def _create_membership_once(self, chama_id: uuid.UUID, data: MembershipCreate) -> Membership:
        if data.member_id is not None:
            member = self.members.get_by_id(data.member_id)
            if member is None:
                raise NotFoundError("Member not found")
            if self.memberships.get_by_chama_and_member(chama_id, member.id) is not None:
                raise ConflictError("This member already belongs to the Chama")
        else:
            member = self._create_member(data.member)

        number = self.memberships.allocate_membership_number(chama_id)
        membership = self.memberships.create(
            chama_id=chama_id, member_id=member.id, membership_number=number
        )
        default_member = self.roles.get_by_name(RoleName.MEMBER)
        self.memberships.add_role(membership.id, default_member)
        chama = get_chama_or_404(self.db, chama_id)
        self.fees.create(membership_id=membership.id, amount=chama.registration_fee_amount)
        self.db.commit()
        return membership

    def update_status(
        self,
        *,
        actor: User,
        chama_id: uuid.UUID,
        membership_id: uuid.UUID,
        status: MembershipStatus,
    ) -> Membership:
        chama = get_chama_or_404(self.db, chama_id)
        actor_membership = authorize_chama_access(self.db, actor=actor, chama_id=chama_id)
        require_roles(actor_membership, (RoleName.CHAIRPERSON,))
        membership = get_target_membership(self.db, chama_id=chama.id, membership_id=membership_id)
        membership.status = status
        self.db.commit()
        return membership

    def _create_member(self, details: MemberDetails):
        if self.members.phone_exists(details.phone_number):
            raise ConflictError("phone_number is already registered to another member")
        if self.members.government_id_exists(details.government_id):
            raise ConflictError("government_id is already registered to another member")
        return self.members.create(details)