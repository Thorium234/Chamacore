"""RegistrationFee service (ADR-003 lifecycle, ADR-022 payment settlement)."""

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, StateError
from app.models.enums import RegistrationFeePaymentStatus, RegistrationFeeStatus, RoleName
from app.models.registration_fee import RegistrationFee
from app.models.user import User
from app.repositories.ledger import LedgerRepository
from app.repositories.registration_fee import RegistrationFeeRepository
from app.repositories.registration_fee_payment import RegistrationFeePaymentRepository
from app.repositories.share import ShareRepository
from app.services.access import (
    authorize_chama_access,
    get_chama_or_404,
    get_target_membership,
    require_role,
    require_roles,
)
from app.services.audit import AuditAction, AuditService
from app.services.finance import get_account_id
from app.services.ledger import (
    CASH_CODE,
    REGISTRATION_FEES_CODE,
    REGISTRATION_FEE_PAYMENT_SOURCE_TYPE,
    LedgerLine,
    LedgerService,
)


class RegistrationFeeService:
    def __init__(self, db: Session):
        self.db = db
        self.fees = RegistrationFeeRepository(db)
        self.payments = RegistrationFeePaymentRepository(db)
        self.ledger = LedgerService(db)
        self.ledger_repo = LedgerRepository(db)
        self.audit = AuditService(db)

    def get_for_membership(
        self, *, actor: User, chama_id: uuid.UUID, membership_id: uuid.UUID
    ) -> RegistrationFee:
        chama = get_chama_or_404(self.db, chama_id)
        authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        membership = get_target_membership(self.db, chama_id=chama.id, membership_id=membership_id)
        fee = self.fees.get_by_membership(membership.id)
        if fee is None:
            raise StateError("This membership has no registration fee record")
        return fee

    def waive(
        self, *, actor: User, chama_id: uuid.UUID, membership_id: uuid.UUID
    ) -> RegistrationFee:
        chama = get_chama_or_404(self.db, chama_id)
        actor_membership = authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        require_role(actor_membership, RoleName.CHAIRPERSON)
        membership = get_target_membership(self.db, chama_id=chama.id, membership_id=membership_id)
        fee = self.fees.get_by_membership(membership.id)
        if fee is None:
            raise StateError("This membership has no registration fee record")
        if fee.status != RegistrationFeeStatus.OWED:
            raise StateError("Only an OWED registration fee can be waived")
        fee.status = RegistrationFeeStatus.WAIVED
        self.audit.record(
            actor=actor,
            chama_id=chama.id,
            action=AuditAction.FEE_WAIVE,
            resource_type="registration_fee",
            resource_id=fee.id,
            payload={"amount": str(fee.amount)},
        )
        self.db.commit()
        return fee

    def pay(self, *, actor: User, chama_id: uuid.UUID, membership_id: uuid.UUID) -> RegistrationFee:
        """Record and post a registration-fee payment (ADR-022).

        Idempotent: paying an already-PAID fee returns the fee with no new
        financial effect. The database partial-unique index on confirmed
        payments makes a second ledger posting impossible.
        """
        chama = get_chama_or_404(self.db, chama_id)
        actor_membership = authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        require_roles(actor_membership, (RoleName.CHAIRPERSON, RoleName.TREASURER))
        membership = get_target_membership(self.db, chama_id=chama.id, membership_id=membership_id)
        fee = self.fees.get_by_membership(membership.id)
        if fee is None:
            raise StateError("This membership has no registration fee record")
        if fee.status == RegistrationFeeStatus.PAID:
            return fee
        if fee.status != RegistrationFeeStatus.OWED:
            raise StateError("Only an OWED registration fee can be paid")

        payment = self.payments.create(
            chama_id=chama.id,
            fee_id=fee.id,
            membership_id=membership.id,
            amount=fee.amount,
            recorded_by_user_id=actor.id,
            note=None,
        )
        fee.status = RegistrationFeeStatus.PAID
        try:
            self.ledger.post_transaction(
                actor=actor,
                chama_id=chama.id,
                source_type=REGISTRATION_FEE_PAYMENT_SOURCE_TYPE,
                source_id=payment.id,
                description=f"Registration fee {fee.id} payment",
                lines=[
                    LedgerLine(
                        account_id=get_account_id(self.db, chama.id, CASH_CODE),
                        debit=fee.amount,
                    ),
                    LedgerLine(
                        account_id=get_account_id(self.db, chama.id, REGISTRATION_FEES_CODE),
                        credit=fee.amount,
                    ),
                ],
            )
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("A confirmed payment already exists for this registration fee") from exc
        self.audit.record(
            actor=actor,
            chama_id=chama.id,
            action=AuditAction.FEE_PAY,
            resource_type="registration_fee_payment",
            resource_id=payment.id,
            payload={"fee_id": str(fee.id), "amount": str(fee.amount)},
        )
        self.db.commit()
        return fee

    def reverse_payment(
        self, *, actor: User, chama_id: uuid.UUID, membership_id: uuid.UUID
    ) -> RegistrationFee:
        """Reverse a PAID fee payment: compensating ledger + fee back to OWED."""
        chama = get_chama_or_404(self.db, chama_id)
        actor_membership = authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        require_role(actor_membership, RoleName.CHAIRPERSON)
        membership = get_target_membership(self.db, chama_id=chama.id, membership_id=membership_id)
        fee = self.fees.get_by_membership(membership.id)
        if fee is None:
            raise StateError("This membership has no registration fee record")
        if fee.status != RegistrationFeeStatus.PAID:
            raise StateError("Only a PAID registration fee can have its payment reversed")

        payment = self.payments.confirmed_by_fee(fee.id)
        if payment is None or payment.status != RegistrationFeePaymentStatus.CONFIRMED:
            raise StateError("This fee has no confirmed payment to reverse")

        posting = self.ledger_repo.get_by_source(REGISTRATION_FEE_PAYMENT_SOURCE_TYPE, payment.id)
        if posting is not None:
            self.ledger.reverse_transaction(
                actor=actor,
                chama_id=chama.id,
                transaction_id=posting.id,
                description=f"Registration fee {fee.id} payment reversal",
            )
        payment.status = RegistrationFeePaymentStatus.REVERSED
        fee.status = RegistrationFeeStatus.OWED
        self.audit.record(
            actor=actor,
            chama_id=chama.id,
            action=AuditAction.FEE_PAY_REVERSAL,
            resource_type="registration_fee_payment",
            resource_id=payment.id,
            payload={"fee_id": str(fee.id)},
        )
        self.db.commit()
        return fee

    def list_payments(
        self, *, actor: User, chama_id: uuid.UUID, membership_id: uuid.UUID
    ) -> list[object]:
        chama = get_chama_or_404(self.db, chama_id)
        authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        membership = get_target_membership(self.db, chama_id=chama.id, membership_id=membership_id)
        fee = self.fees.get_by_membership(membership.id)
        if fee is None:
            raise StateError("This membership has no registration fee record")
        return self.payments.list_by_fee(fee.id)