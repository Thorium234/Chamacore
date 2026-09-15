"""Membership endpoints."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.membership import MembershipCreate, MembershipOut, MembershipStatusUpdate
from app.services.membership import MembershipService

router = APIRouter(tags=["memberships"])


@router.get("/chamas/{chama_id}/memberships", response_model=list[MembershipOut])
def list_memberships(
    chama_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    memberships = MembershipService(db).list_by_chama(actor=actor, chama_id=chama_id)
    return [MembershipOut.model_validate(m) for m in memberships]


@router.post(
    "/chamas/{chama_id}/memberships",
    response_model=MembershipOut,
    status_code=status.HTTP_201_CREATED,
)
def create_membership(
    chama_id: uuid.UUID,
    data: MembershipCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    membership = MembershipService(db).create_membership(actor=actor, chama_id=chama_id, data=data)
    return MembershipOut.model_validate(membership)


@router.patch(
    "/chamas/{chama_id}/memberships/{membership_id}/status",
    response_model=MembershipOut,
)
def update_membership_status(
    chama_id: uuid.UUID,
    membership_id: uuid.UUID,
    data: MembershipStatusUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    membership = MembershipService(db).update_status(
        actor=actor, chama_id=chama_id, membership_id=membership_id, status=data.status
    )
    return MembershipOut.model_validate(membership)