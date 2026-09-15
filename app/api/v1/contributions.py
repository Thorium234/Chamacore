"""Contribution endpoints."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.membership import ContributionCreate, ContributionOut, ContributionReverseRequest
from app.services.contribution import ContributionService

router = APIRouter(tags=["contributions"])


@router.post(
    "/chamas/{chama_id}/contributions",
    response_model=ContributionOut,
    status_code=status.HTTP_201_CREATED,
)
def record_contribution(
    chama_id: uuid.UUID,
    data: ContributionCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    contribution = ContributionService(db).record(actor=actor, chama_id=chama_id, data=data)
    return ContributionOut.model_validate(contribution)


@router.post("/chamas/{chama_id}/contributions/{contribution_id}/confirm", response_model=ContributionOut)
def confirm_contribution(
    chama_id: uuid.UUID,
    contribution_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    contribution = ContributionService(db).confirm(actor=actor, chama_id=chama_id, contribution_id=contribution_id)
    return ContributionOut.model_validate(contribution)


@router.post("/chamas/{chama_id}/contributions/{contribution_id}/reverse", response_model=ContributionOut)
def reverse_contribution(
    chama_id: uuid.UUID,
    contribution_id: uuid.UUID,
    data: ContributionReverseRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    contribution = ContributionService(db).reverse(
        actor=actor, chama_id=chama_id, contribution_id=contribution_id, note=data.note
    )
    return ContributionOut.model_validate(contribution)


@router.get("/chamas/{chama_id}/contributions", response_model=list[ContributionOut])
def list_contributions(
    chama_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    contributions = ContributionService(db).list_by_chama(actor=actor, chama_id=chama_id)
    return [ContributionOut.model_validate(c) for c in contributions]