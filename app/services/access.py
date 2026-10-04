"""Authorization helpers shared by services."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, PermissionDeniedError, StateError
from app.models.chama import Chama
from app.models.enums import ChamaStatus, MembershipStatus, RoleName
from app.models.membership import Membership
from app.models.user import User

LEADERSHIP_ROLES = (RoleName.CHAIRPERSON, RoleName.TREASURER, RoleName.SECRETARY)


def get_chama_or_404(db: Session, chama_id: uuid.UUID) -> Chama:
    chama = db.get(Chama, chama_id)
    if chama is None:
        raise NotFoundError("Chama not found")
    return chama


def authorize_chama_access(db: Session, *, actor: User, chama_id: uuid.UUID) -> Membership:
    """Return the actor's active membership in the Chama, or raise 403."""
    if actor.member_id is None:
        raise PermissionDeniedError("You are not an active member of this Chama")
    stmt = select(Membership).where(
        Membership.member_id == actor.member_id,
        Membership.chama_id == chama_id,
        Membership.status == MembershipStatus.ACTIVE,
    )
    membership = db.scalars(stmt).first()
    if membership is None:
        raise PermissionDeniedError("You are not an active member of this Chama")
    return membership


def authorize_chama_write(db: Session, *, actor: User, chama_id: uuid.UUID) -> Membership:
    """Authorize a member mutation only while the Chama is active."""
    chama = get_chama_or_404(db, chama_id)
    membership = authorize_chama_access(db, actor=actor, chama_id=chama_id)
    if chama.status != ChamaStatus.ACTIVE:
        raise StateError("This Chama is read-only until a platform administrator activates it")
    return membership


def require_roles(membership: Membership, roles: tuple[RoleName, ...]) -> None:
    if not any(membership.has_role(role) for role in roles):
        names = ", ".join(role.value for role in roles)
        raise PermissionDeniedError(f"This action requires one of the roles: {names}")


def require_own_or_leadership(
    caller: Membership,
    target_membership_id: uuid.UUID,
    *,
    resource: str,
) -> None:
    """Allow a member to read their own financial data; leaders may read group data."""
    if caller.id == target_membership_id:
        return
    if any(caller.has_role(role) for role in LEADERSHIP_ROLES):
        return
    raise PermissionDeniedError(f"You may only view your own {resource}")


def require_role(membership: Membership, role: RoleName) -> None:
    if not membership.has_role(role):
        raise PermissionDeniedError(f"This action requires the {role.value} role")


def get_target_membership(db: Session, *, chama_id: uuid.UUID, membership_id: uuid.UUID) -> Membership:
    membership = db.get(Membership, membership_id)
    if membership is None or membership.chama_id != chama_id:
        raise NotFoundError("Membership not found in this Chama")
    return membership


def is_platform_admin(db: Session, *, user: User) -> bool:
    """Return True when the user holds the global PLATFORM_ADMIN grant.

    ``PLATFORM_ADMIN`` is deliberately not a Chama role: it is stored on
    ``user_platform_roles`` so a platform administrator does not have to be a
    member of every Chama they oversee.
    """
    if not user.is_active:
        return False
    from app.repositories.user_platform_role import UserPlatformRoleRepository

    return UserPlatformRoleRepository(db).has_role(
        user_id=user.id, role=RoleName.PLATFORM_ADMIN
    )


def require_platform_admin(db: Session, *, user: User) -> None:
    if not is_platform_admin(db, user=user):
        raise PermissionDeniedError("This action requires the PLATFORM_ADMIN role")
