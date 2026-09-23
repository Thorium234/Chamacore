"""Loan and loan repayment endpoints (ADR-020)."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.loan import (
    LoanApplyRequest,
    LoanOut,
    LoanRejectRequest,
    LoanRepaymentCreate,
    LoanRepaymentOut,
    LoanRepaymentReverseRequest,
)
from app.services.loan import LoanService

router = APIRouter(tags=["loans"])


def _serialize(service: LoanService, loan) -> LoanOut:
    return LoanOut.model_validate(service.serialize(loan))


@router.post("/chamas/{chama_id}/loans", response_model=LoanOut, status_code=status.HTTP_201_CREATED)
def apply_for_loan(
    chama_id: uuid.UUID,
    data: LoanApplyRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    service = LoanService(db)
    loan = service.apply(actor=actor, chama_id=chama_id, data=data)
    return _serialize(service, loan)


@router.get("/chamas/{chama_id}/loans", response_model=list[LoanOut])
def list_loans(
    chama_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    service = LoanService(db)
    loans = service.list_by_chama(actor=actor, chama_id=chama_id)
    return [_serialize(service, loan) for loan in loans]


@router.get("/chamas/{chama_id}/memberships/{membership_id}/loans", response_model=list[LoanOut])
def list_member_loans(
    chama_id: uuid.UUID,
    membership_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    service = LoanService(db)
    loans = service.list_by_membership(
        actor=actor, chama_id=chama_id, membership_id=membership_id
    )
    return [_serialize(service, loan) for loan in loans]


@router.post("/chamas/{chama_id}/loans/{loan_id}/submit", response_model=LoanOut)
def submit_loan(
    chama_id: uuid.UUID,
    loan_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    service = LoanService(db)
    loan = service.submit(actor=actor, chama_id=chama_id, loan_id=loan_id)
    return _serialize(service, loan)


@router.post("/chamas/{chama_id}/loans/{loan_id}/approve", response_model=LoanOut)
def approve_loan(
    chama_id: uuid.UUID,
    loan_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    service = LoanService(db)
    loan = service.approve(actor=actor, chama_id=chama_id, loan_id=loan_id)
    return _serialize(service, loan)


@router.post("/chamas/{chama_id}/loans/{loan_id}/reject", response_model=LoanOut)
def reject_loan(
    chama_id: uuid.UUID,
    loan_id: uuid.UUID,
    data: LoanRejectRequest | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    service = LoanService(db)
    loan = service.reject(
        actor=actor,
        chama_id=chama_id,
        loan_id=loan_id,
        note=(data.note if data is not None else None),
    )
    return _serialize(service, loan)


@router.post("/chamas/{chama_id}/loans/{loan_id}/cancel", response_model=LoanOut)
def cancel_loan(
    chama_id: uuid.UUID,
    loan_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    service = LoanService(db)
    loan = service.cancel(actor=actor, chama_id=chama_id, loan_id=loan_id)
    return _serialize(service, loan)


@router.post("/chamas/{chama_id}/loans/{loan_id}/disburse", response_model=LoanOut)
def disburse_loan(
    chama_id: uuid.UUID,
    loan_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    service = LoanService(db)
    loan = service.disburse(actor=actor, chama_id=chama_id, loan_id=loan_id)
    return _serialize(service, loan)


@router.post("/chamas/{chama_id}/loans/{loan_id}/repayments", response_model=LoanOut, status_code=status.HTTP_201_CREATED)
def record_loan_repayment(
    chama_id: uuid.UUID,
    loan_id: uuid.UUID,
    data: LoanRepaymentCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    service = LoanService(db)
    loan = service.record_repayment(
        actor=actor, chama_id=chama_id, loan_id=loan_id, amount=data.amount, note=data.note
    )
    return _serialize(service, loan)


@router.get("/chamas/{chama_id}/loans/{loan_id}/repayments", response_model=list[LoanRepaymentOut])
def list_loan_repayments(
    chama_id: uuid.UUID,
    loan_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    service = LoanService(db)
    repayments = service.list_repayments(actor=actor, chama_id=chama_id, loan_id=loan_id)
    return [LoanRepaymentOut.model_validate(r) for r in repayments]


@router.post("/chamas/{chama_id}/loans/{loan_id}/repayments/{repayment_id}/reverse", response_model=LoanOut)
def reverse_loan_repayment(
    chama_id: uuid.UUID,
    loan_id: uuid.UUID,
    repayment_id: uuid.UUID,
    data: LoanRepaymentReverseRequest | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    service = LoanService(db)
    loan = service.reverse_repayment(
        actor=actor,
        chama_id=chama_id,
        loan_id=loan_id,
        repayment_id=repayment_id,
        note=(data.note if data is not None else None),
    )
    return _serialize(service, loan)