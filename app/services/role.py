"""Role service."""

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, StateError
from app.models.enums import RoleName
from app.models.membership import Membership
from app.models.role import Role
from app.models.user import User
from app.repositories.membership import MembershipRepository
from app.repositories.role import RoleRepository
from app.services.access import (
    LEADERSHIP_ROLES,
    authorize_chama_access,
    get_chama_or_404,
    get_target_membership,
    require_role,
)
from app.services.audit import AuditAction, AuditService


class RoleService:
    def __init__(self, db: Session):
        self.db = db
        self.memberships = MembershipRepository(db)
        self.roles = RoleRepository(db)
        self.audit = AuditService(db)

    def list_chama_roles(self, *, actor: User, chama_id: uuid.UUID) -> list[Role]:
        chama = get_chama_or_404(self.db, chama_id)
        authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        return self.roles.list_all()

    def assign_role(
        self, *, actor: User, chama_id: uuid.UUID, membership_id: uuid.UUID, role: RoleName
    ) -> Membership:
        chama = get_chama_or_404(self.db, chama_id)
        actor_membership = authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        require_role(actor_membership, RoleName.CHAIRPERSON)
        target = get_target_membership(self.db, chama_id=chama.id, membership_id=membership_id)

        if role == RoleName.MEMBER:
            raise StateError("The MEMBER role is assigned automatically and cannot be assigned manually")
        if any(target.has_role(existing) for existing in LEADERSHIP_ROLES):
            raise StateError("This membership already holds a leadership role")
        if role == RoleName.CHAIRPERSON and self._has_chairperson(chama.id, exclude=target.id):
            raise StateError("This Chama already has a chairperson")

        role_object = self.roles.get_by_name(role)
        if role_object is None:
            raise NotFoundError("Role not found")
        try:
            self.memberships.add_role(target.id, role_object)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("Role is already assigned to this membership") from exc
        self.db.expire(target)
        self.audit.record_commit(
            actor=actor,
            chama_id=chama.id,
            action=AuditAction.ROLE_ASSIGN,
            resource_type="membership",
            resource_id=target.id,
            payload={"role": role.value},
        )
        return target

    def remove_role(
        self, *, actor: User, chama_id: uuid.UUID, membership_id: uuid.UUID, role: RoleName
    ) -> Membership:
        chama = get_chama_or_404(self.db, chama_id)
        actor_membership = authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        require_role(actor_membership, RoleName.CHAIRPERSON)
        target = get_target_membership(self.db, chama_id=chama.id, membership_id=membership_id)

        if role == RoleName.MEMBER:
            raise StateError("The MEMBER role is assigned automatically and cannot be removed")
        role_object = self.roles.get_by_name(role)
        if role_object is None:
            raise NotFoundError("Role not found")
        if not self.memberships.remove_role(target.id, role_object):
            raise StateError("This membership does not hold the requested role")
        self.db.commit()
        self.db.expire(target)
        self.audit.record_commit(
            actor=actor,
            chama_id=chama.id,
            action=AuditAction.ROLE_REMOVE,
            resource_type="membership",
            resource_id=target.id,
            payload={"role": role.value},
        )
        return target

    def _has_chairperson(self, chama_id: uuid.UUID, *, exclude: uuid.UUID) -> bool:
        for membership in self.memberships.list_by_chama(chama_id):
            if membership.id == exclude:
                continue
            if membership.has_role(RoleName.CHAIRPERSON):
                return True
        return False