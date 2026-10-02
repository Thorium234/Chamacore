"""Platform administration service: cross-Chama oversight (F3).

Every method requires the global ``PLATFORM_ADMIN`` grant, which lives on
``user_platform_roles`` rather than on a Chama membership. Platform
administration is read-mostly plus Chama lifecycle control; it never touches
financial records, and a Chama's own roles and memberships remain the
authority inside the Chama.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, StateError
from app.models.chama import Chama
from app.models.enums import ChamaStatus, MembershipStatus, RoleName
from app.models.member import Member
from app.models.membership import Membership
from app.models.user import User
from app.models.user_platform_role import UserPlatformRole
from app.repositories.user import UserRepository
from app.repositories.user_platform_role import UserPlatformRoleRepository
from app.schemas.platform import (
    PlatformChamaOut,
    PlatformChamaStatusUpdate,
    PlatformStatsOut,
    PlatformUserOut,
)
from app.services.access import require_platform_admin
from app.services.audit import AuditAction, AuditService

# DISSOLVED is terminal: a dissolved Chama cannot be revived, so that financial
# history stays interpretable.
TERMINAL_STATUSES = frozenset({ChamaStatus.DISSOLVED})

ALLOWED_TRANSITIONS: dict[ChamaStatus, frozenset[ChamaStatus]] = {
    ChamaStatus.PENDING: frozenset(
        {ChamaStatus.ACTIVE, ChamaStatus.SUSPENDED, ChamaStatus.DISSOLVED}
    ),
    ChamaStatus.ACTIVE: frozenset({ChamaStatus.SUSPENDED, ChamaStatus.DISSOLVED}),
    ChamaStatus.SUSPENDED: frozenset({ChamaStatus.ACTIVE, ChamaStatus.DISSOLVED}),
    ChamaStatus.DISSOLVED: frozenset(),
    # Legacy alias: treated as SUSPENDED for transitions.
    ChamaStatus.INACTIVE: frozenset({ChamaStatus.ACTIVE, ChamaStatus.SUSPENDED, ChamaStatus.DISSOLVED}),
}


def _canonical(status: ChamaStatus) -> ChamaStatus:
    return ChamaStatus.SUSPENDED if status == ChamaStatus.INACTIVE else status


class PlatformService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.platform_roles = UserPlatformRoleRepository(db)
        self.audit = AuditService(db)

    # -- Chama lifecycle ------------------------------------------------------

    def list_chamas(
        self,
        *,
        actor: User,
        status: ChamaStatus | None = None,
        search: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[PlatformChamaOut]:
        require_platform_admin(self.db, user=actor)
        stmt = select(Chama)
        if status is not None:
            if status == ChamaStatus.INACTIVE:
                stmt = stmt.where(Chama.status == ChamaStatus.INACTIVE)
            else:
                stmt = stmt.where(Chama.status == status)
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(Chama.name.ilike(pattern))
        stmt = stmt.order_by(Chama.created_at.desc(), Chama.id)
        if limit is not None:
            stmt = stmt.limit(limit).offset(offset)
        chamas = list(self.db.scalars(stmt))
        return [self._chama_out(chama) for chama in chamas]

    def get_chama(self, *, actor: User, chama_id: uuid.UUID) -> PlatformChamaOut:
        require_platform_admin(self.db, user=actor)
        chama = self._get_chama(chama_id)
        return self._chama_out(chama)

    def update_chama_status(
        self,
        *,
        actor: User,
        chama_id: uuid.UUID,
        data: PlatformChamaStatusUpdate,
    ) -> PlatformChamaOut:
        require_platform_admin(self.db, user=actor)
        chama = self._get_chama(chama_id)
        current = _canonical(chama.status)
        target = _canonical(data.status)
        if current == target:
            return self._chama_out(chama)
        if current in TERMINAL_STATUSES:
            raise StateError("A dissolved Chama cannot change status")
        if target not in ALLOWED_TRANSITIONS[current]:
            raise StateError(f"A Chama cannot move from {current.value} to {target.value}")

        previous = chama.status
        chama.status = data.status
        self.db.commit()
        self.audit.record_commit(
            actor=actor,
            chama_id=chama.id,
            action=AuditAction.PLATFORM_CHAMA_STATUS_CHANGE,
            resource_type="chama",
            resource_id=chama.id,
            payload={
                "from": previous.value,
                "to": data.status.value,
                "reason": data.reason,
            },
        )
        return self._chama_out(chama)

    # -- Users and grants -----------------------------------------------------

    def list_users(
        self,
        *,
        actor: User,
        limit: int | None = None,
        offset: int = 0,
        search: str | None = None,
    ) -> list[PlatformUserOut]:
        require_platform_admin(self.db, user=actor)
        stmt = select(User)
        if search:
            stmt = stmt.where(User.email.ilike(f"%{search.strip()}%"))
        stmt = stmt.order_by(User.created_at.desc(), User.id)
        if limit is not None:
            stmt = stmt.limit(limit).offset(offset)
        return [self._user_out(user) for user in self.db.scalars(stmt)]

    def grant_platform_admin(
        self, *, actor: User, user_id: uuid.UUID, role: RoleName = RoleName.PLATFORM_ADMIN
    ) -> PlatformUserOut:
        require_platform_admin(self.db, user=actor)
        if role != RoleName.PLATFORM_ADMIN:
            raise StateError("Only PLATFORM_ADMIN can be granted on this endpoint")
        target = self.users.get_by_id(user_id)
        if target is None:
            raise NotFoundError("User not found")
        if self.platform_roles.has_role(user_id=user_id, role=role):
            raise ConflictError("This user already holds PLATFORM_ADMIN")
        self.platform_roles.grant(
            user_id=user_id,
            role=role,
            granted_by_user_id=actor.id,
            granted_at=datetime.now(timezone.utc),
        )
        self.db.commit()
        self.audit.record_commit(
            actor=actor,
            chama_id=None,
            action=AuditAction.PLATFORM_ADMIN_GRANTED,
            resource_type="user",
            resource_id=user_id,
            payload={"role": role.value},
        )
        return self._user_out(target)

    def revoke_platform_admin(
        self, *, actor: User, user_id: uuid.UUID, role: RoleName = RoleName.PLATFORM_ADMIN
    ) -> PlatformUserOut:
        require_platform_admin(self.db, user=actor)
        target = self.users.get_by_id(user_id)
        if target is None:
            raise NotFoundError("User not found")
        assignment = self.platform_roles.get(user_id=user_id, role=role)
        if assignment is None:
            raise NotFoundError("This user does not hold PLATFORM_ADMIN")
        if user_id == actor.id:
            raise StateError("You cannot revoke your own PLATFORM_ADMIN grant")
        remaining = [
            admin_id
            for admin_id in self.platform_roles.list_admin_user_ids(role=role)
            if admin_id != user_id
        ]
        if not remaining:
            raise StateError("The last PLATFORM_ADMIN cannot be revoked")
        self.db.delete(assignment)
        self.db.commit()
        self.audit.record_commit(
            actor=actor,
            chama_id=None,
            action=AuditAction.PLATFORM_ADMIN_REVOKED,
            resource_type="user",
            resource_id=user_id,
            payload={"role": role.value},
        )
        return self._user_out(target)

    def require_password_change(
        self, *, actor: User, user_id: uuid.UUID, reason: str | None = None
    ) -> PlatformUserOut:
        require_platform_admin(self.db, user=actor)
        target = self.users.get_by_id(user_id)
        if target is None:
            raise NotFoundError("User not found")
        target.must_change_password = True
        self.db.commit()
        self.audit.record_commit(
            actor=actor,
            chama_id=None,
            action=AuditAction.AUTH_PASSWORD_CHANGE_REQUIRED,
            resource_type="user",
            resource_id=target.id,
            payload={"reason": reason} if reason else None,
        )
        return self._user_out(target)

    # -- Dashboard ------------------------------------------------------------

    def stats(self, *, actor: User) -> PlatformStatsOut:
        require_platform_admin(self.db, user=actor)
        return PlatformStatsOut(
            total_chamas=self._chama_count(),
            active_chamas=self._chama_count(ChamaStatus.ACTIVE),
            pending_chamas=self._chama_count(ChamaStatus.PENDING),
            suspended_chamas=self._chama_count(ChamaStatus.SUSPENDED)
            + self._chama_count(ChamaStatus.INACTIVE),
            dissolved_chamas=self._chama_count(ChamaStatus.DISSOLVED),
            total_users=self._count(User),
            total_members=self._count(Member),
            platform_admins=self._count(
                UserPlatformRole, where=UserPlatformRole.role == RoleName.PLATFORM_ADMIN
            ),
        )

    # -- internals ------------------------------------------------------------

    def _chama_count(self, status: ChamaStatus | None = None) -> int:
        stmt = select(func.count()).select_from(Chama)
        if status is not None:
            stmt = stmt.where(Chama.status == status)
        return int(self.db.scalar(stmt) or 0)

    def _count(self, entity, *, where=None) -> int:
        stmt = select(func.count()).select_from(entity)
        if where is not None:
            stmt = stmt.where(where)
        return int(self.db.scalar(stmt) or 0)

    def _get_chama(self, chama_id: uuid.UUID) -> Chama:
        chama = self.db.get(Chama, chama_id)
        if chama is None:
            raise NotFoundError("Chama not found")
        return chama

    def _chama_out(self, chama: Chama) -> PlatformChamaOut:
        total = int(
            self.db.scalar(
                select(func.count())
                .select_from(Membership)
                .where(Membership.chama_id == chama.id)
            )
            or 0
        )
        active = int(
            self.db.scalar(
                select(func.count())
                .select_from(Membership)
                .where(
                    Membership.chama_id == chama.id,
                    Membership.status == MembershipStatus.ACTIVE,
                )
            )
            or 0
        )
        out = PlatformChamaOut.model_validate(chama)
        out.membership_count = total
        out.active_member_count = active
        return out

    def _user_out(self, user: User) -> PlatformUserOut:
        out = PlatformUserOut.model_validate(user)
        out.platform_roles = [assignment.role for assignment in self.platform_roles.list_for_user(user_id=user.id)]
        return out