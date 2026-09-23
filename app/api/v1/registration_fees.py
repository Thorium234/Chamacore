"""Registration fee endpoints (ADR-003 lifecycle, ADR-022 payment settlement)."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.membership import RegistrationFeeOut
from app.schemas.registration_fee import RegistrationFeePaymentOut
from app.services.registration_fee import RegistrationFeeService

router = APIRouter(tags=["registration-fees"])


@router.get("/chamas/{chama_id}/memberships/{membership_id}/registration-fee", response_model=RegistrationFeeOut)
def get_registration_fee(
    chama_id: uuid.UUID,
    membership_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    fee = RegistrationFeeService(db).get_for_membership(
        actor=actor, chama_id=chama_id, membership_id=membership_id
    )
    return RegistrationFeeOut.model_validate(fee)


@router.post("/chamas/{chama_id}/memberships/{membership_id}/registration-fee/waive", response_model=RegistrationFeeOut)
def waive_registration_fee(
    chama_id: uuid.UUID,
    membership_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    fee = RegistrationFeeService(db).waive(actor=actor, chama_id=chama_id, membership_id=membership_id)
    return RegistrationFeeOut.model_validate(fee)


@router.post(
    "/chamas/{chama_id}/memberships/{membership_id}/registration-fee/pay",
    response_model=RegistrationFeeOut,
    status_code=status.HTTP_200_OK,
)
def pay_registration_fee(
    chama_id: uuid.UUID,
    membership_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    fee = RegistrationFeeService(db).pay(actor=actor, chama_id=chama_id, membership_id=membership_id)
    return RegistrationFeeOut.model_validate(fee)


@router.post(
    "/chamas/{chama_id}/memberships/{membership_id}/registration-fee/payment/reverse",
    response_model=RegistrationFeeOut,
)
def reverse_registration_fee_payment(
    chama_id: uuid.UUID,
    membership_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    fee = RegistrationFeeService(db).reverse_payment(
        actor=actor, chama_id=chama_id, membership_id=membership_id
    )
    return RegistrationFeeOut.model_validate(fee)


@router.get(
    "/chamas/{chama_id}/memberships/{membership_id}/registration-fee/payments",
    response_model=list[RegistrationFeePaymentOut],
)
def list_registration_fee_payments(
    chama_id: uuid.UUID,
    membership_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    payments = RegistrationFeeService(db).list_payments(
        actor=actor, chama_id=chama_id, membership_id=membership_id
    )
    return [RegistrationFeePaymentOut.model_validate(p) for p in payments]