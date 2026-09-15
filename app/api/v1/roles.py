"""Role endpoints."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.enums import RoleName
from app.models.user import User
from app.schemas.membership import MembershipOut, RoleAssignRequest, RoleOut
from app.services.role import RoleService

router = APIRouter(tags=["roles"])


@router.get("/chamas/{chama_id}/roles", response_model=list[RoleOut])
def list_roles(
    chama_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    roles = RoleService(db).list_chama_roles(actor=actor, chama_id=chama_id)
    return [RoleOut.model_validate(role) for role in roles]


@router.post(
    "/chamas/{chama_id}/memberships/{membership_id}/roles",
    response_model=MembershipOut,
    status_code=status.HTTP_201_CREATED,
)
def assign_role(
    chama_id: uuid.UUID,
    membership_id: uuid.UUID,
    data: RoleAssignRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    membership = RoleService(db).assign_role(
        actor=actor, chama_id=chama_id, membership_id=membership_id, role=data.role
    )
    return MembershipOut.model_validate(membership)


@router.delete(
    "/chamas/{chama_id}/memberships/{membership_id}/roles/{role_name}",
    response_model=MembershipOut,
)
def remove_role(
    chama_id: uuid.UUID,
    membership_id: uuid.UUID,
    role_name: RoleName,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    membership = RoleService(db).remove_role(
        actor=actor, chama_id=chama_id, membership_id=membership_id, role=role_name
    )
    return MembershipOut.model_validate(membership)