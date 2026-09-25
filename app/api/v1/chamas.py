"""Chama endpoints."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.enums import RoleName
from app.models.user import User
from app.repositories.membership import MembershipRepository
from app.schemas.chama import ChamaCreate, ChamaCreatedOut, ChamaOut, ChamaUpdate
from app.services.chama import ChamaService

router = APIRouter(tags=["chamas"])


@router.post("/chamas", response_model=ChamaCreatedOut, status_code=status.HTTP_201_CREATED)
def create_chama(data: ChamaCreate, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    chama = ChamaService(db).create_chama(user=actor, data=data)
    out = ChamaCreatedOut.model_validate(chama)
    if actor.member_id is not None:
        membership = MembershipRepository(db).get_by_chama_and_member(chama.id, actor.member_id)
        if membership is not None:
            out.membership_id = membership.id
            out.roles = [RoleName(role.name) for role in membership.roles]
    return out


@router.get("/chamas", response_model=list[ChamaOut])
def list_chamas(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    chamas = ChamaService(db).list_my_chamas(actor=actor)
    return [ChamaOut.model_validate(c) for c in chamas]


@router.get("/chamas/{chama_id}", response_model=ChamaOut)
def get_chama(
    chama_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    chama = ChamaService(db).get_chama(actor=actor, chama_id=chama_id)
    return ChamaOut.model_validate(chama)


@router.patch("/chamas/{chama_id}", response_model=ChamaOut)
def update_chama(
    chama_id: uuid.UUID,
    data: ChamaUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    chama = ChamaService(db).update_chama(actor=actor, chama_id=chama_id, data=data)
    return ChamaOut.model_validate(chama)