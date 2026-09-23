"""Payout endpoints (ADR-021)."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.payout import PayoutFailRequest, PayoutOut, PayoutRequestCreate
from app.services.payout import PayoutService

router = APIRouter(tags=["payouts"])


@router.post("/chamas/{chama_id}/payouts", response_model=PayoutOut, status_code=status.HTTP_201_CREATED)
def request_payout(
    chama_id: uuid.UUID,
    data: PayoutRequestCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    payout = PayoutService(db).request_payout(actor=actor, chama_id=chama_id, data=data)
    return PayoutOut.model_validate(payout)


@router.get("/chamas/{chama_id}/payouts", response_model=list[PayoutOut])
def list_payouts(
    chama_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    payouts = PayoutService(db).list_by_chama(actor=actor, chama_id=chama_id)
    return [PayoutOut.model_validate(p) for p in payouts]


@router.post("/chamas/{chama_id}/payouts/{payout_id}/approve", response_model=PayoutOut)
def approve_payout(
    chama_id: uuid.UUID,
    payout_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    payout = PayoutService(db).approve(actor=actor, chama_id=chama_id, payout_id=payout_id)
    return PayoutOut.model_validate(payout)


@router.post("/chamas/{chama_id}/payouts/{payout_id}/reject", response_model=PayoutOut)
def reject_payout(
    chama_id: uuid.UUID,
    payout_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    payout = PayoutService(db).reject(actor=actor, chama_id=chama_id, payout_id=payout_id)
    return PayoutOut.model_validate(payout)


@router.post("/chamas/{chama_id}/payouts/{payout_id}/process", response_model=PayoutOut)
def process_payout(
    chama_id: uuid.UUID,
    payout_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    payout = PayoutService(db).process(actor=actor, chama_id=chama_id, payout_id=payout_id)
    return PayoutOut.model_validate(payout)


@router.post("/chamas/{chama_id}/payouts/{payout_id}/complete", response_model=PayoutOut)
def complete_payout(
    chama_id: uuid.UUID,
    payout_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    payout = PayoutService(db).complete(actor=actor, chama_id=chama_id, payout_id=payout_id)
    return PayoutOut.model_validate(payout)


@router.post("/chamas/{chama_id}/payouts/{payout_id}/fail", response_model=PayoutOut)
def fail_payout(
    chama_id: uuid.UUID,
    payout_id: uuid.UUID,
    data: PayoutFailRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    payout = PayoutService(db).fail(
        actor=actor,
        chama_id=chama_id,
        payout_id=payout_id,
        failure_reason=data.failure_reason,
    )
    return PayoutOut.model_validate(payout)


@router.post("/chamas/{chama_id}/payouts/{payout_id}/reverse", response_model=PayoutOut)
def reverse_payout(
    chama_id: uuid.UUID,
    payout_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    payout = PayoutService(db).reverse(actor=actor, chama_id=chama_id, payout_id=payout_id)
    return PayoutOut.model_validate(payout)