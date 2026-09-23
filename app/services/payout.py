"""Payout service (ADR-021).

Implements the controlled payout lifecycle (REQUESTED â†’ APPROVED â†’ PROCESSING â†’
COMPLETED with REJECTED/FAILED/REVERSED paths), share-value and cash limits,
CHAIRPERSON approval with no self-approval, and atomic idempotent ledger
posting at completion.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, StateError
from app.models.enums import PayoutStatus, RoleName
from app.models.payout import Payout
from app.models.user import User
from app.repositories.ledger import LedgerRepository
from app.repositories.payout import PayoutRepository
from app.schemas.payout import PayoutRequestCreate
from app.services.access import (
    authorize_chama_access,
    get_chama_or_404,
    require_role,
    require_roles,
)
from app.services.audit import AuditAction, AuditService
from app.services.finance import available_chama_cash, get_account_id, member_share_value
from app.services.ledger import (
    CASH_CODE,
    PAYOUT_COMPLETION_SOURCE_TYPE,
    SHARE_CAPITAL_CODE,
    LedgerLine,
    LedgerService,
)


class PayoutService:
    def __init__(self, db: Session):
        self.db = db
        self.payouts = PayoutRepository(db)
        self.ledger = LedgerService(db)
        self.ledger_repo = LedgerRepository(db)
        self.audit = AuditService(db)

    def request_payout(
        self, *, actor: User, chama_id: uuid.UUID, data: PayoutRequestCreate
    ) -> Payout:
        chama = get_chama_or_404(self.db, chama_id)
        membership = authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        available = self._available_share_value(membership.id)
        if data.amount > available:
            raise StateError(
                "Payout amount cannot exceed the member's outstanding share value"
            )
        if data.amount > available_chama_cash(self.db, chama.id):
            raise StateError(
                "Payout amount cannot exceed the Chama's available cash"
            )

        payout = Payout(
            chama_id=chama.id,
            membership_id=membership.id,
            amount=data.amount,
            status=PayoutStatus.REQUESTED,
            requested_by_user_id=actor.id,
            note=data.note,
        )
        self.db.add(payout)
        self.db.flush()
        self.audit.record(
            actor=actor,
            chama_id=chama.id,
            action=AuditAction.PAYOUT_REQUEST,
            resource_type="payout",
            resource_id=payout.id,
            payload={"amount": str(data.amount)},
        )
        self.db.commit()
        return payout

    def approve(self, *, actor: User, chama_id: uuid.UUID, payout_id: uuid.UUID) -> Payout:
        chama = get_chama_or_404(self.db, chama_id)
        actor_membership = authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        require_role(actor_membership, RoleName.CHAIRPERSON)
        payout = self._get_chama_payout(chama.id, payout_id)
        self._forbid_self_action(payout, actor_membership.id, "approve")
        self._transition(payout, (PayoutStatus.REQUESTED,), PayoutStatus.APPROVED)
        payout.approved_by_user_id = actor.id
        payout.approved_at = datetime.now()
        self.audit.record(
            actor=actor,
            chama_id=chama.id,
            action=AuditAction.PAYOUT_APPROVE,
            resource_type="payout",
            resource_id=payout.id,
            payload={"amount": str(payout.amount)},
        )
        self.db.commit()
        return payout

    def reject(self, *, actor: User, chama_id: uuid.UUID, payout_id: uuid.UUID) -> Payout:
        chama = get_chama_or_404(self.db, chama_id)
        actor_membership = authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        require_role(actor_membership, RoleName.CHAIRPERSON)
        payout = self._get_chama_payout(chama.id, payout_id)
        self._forbid_self_action(payout, actor_membership.id, "reject")
        self._transition(payout, (PayoutStatus.REQUESTED,), PayoutStatus.REJECTED)
        self.audit.record(
            actor=actor,
            chama_id=chama.id,
            action=AuditAction.PAYOUT_REJECT,
            resource_type="payout",
            resource_id=payout.id,
        )
        self.db.commit()
        return payout

    def process(self, *, actor: User, chama_id: uuid.UUID, payout_id: uuid.UUID) -> Payout:
        chama = get_chama_or_404(self.db, chama_id)
        actor_membership = authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        require_roles(actor_membership, (RoleName.CHAIRPERSON, RoleName.TREASURER))
        payout = self._get_chama_payout(chama.id, payout_id)
        self._transition(payout, (PayoutStatus.APPROVED,), PayoutStatus.PROCESSING)
        payout.processed_by_user_id = actor.id
        payout.processed_at = datetime.now()
        self.audit.record(
            actor=actor,
            chama_id=chama.id,
            action=AuditAction.PAYOUT_PROCESS,
            resource_type="payout",
            resource_id=payout.id,
        )
        self.db.commit()
        return payout

    def complete(self, *, actor: User, chama_id: uuid.UUID, payout_id: uuid.UUID) -> Payout:
        """Complete a PROCESSING payout atomically with its ledger posting.

        Idempotent: a retry returns the COMPLETED payout without a second
        financial effect (the ledger source is unique per payout).
        """
        chama = get_chama_or_404(self.db, chama_id)
        actor_membership = authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        require_roles(actor_membership, (RoleName.CHAIRPERSON, RoleName.TREASURER))
        payout = self._get_chama_payout(chama.id, payout_id)

        posting = self.ledger_repo.get_by_source(PAYOUT_COMPLETION_SOURCE_TYPE, payout.id)
        if payout.status == PayoutStatus.COMPLETED:
            if posting is None:
                raise StateError("Completed payout is missing its ledger transaction")
            return payout

        self._transition(payout, (PayoutStatus.PROCESSING,), PayoutStatus.COMPLETED)
        if payout.amount > available_chama_cash(self.db, chama.id):
            raise StateError("Insufficient available Chama cash to complete this payout")
        payout.completed_by_user_id = actor.id
        payout.completed_at = datetime.now()

        self.ledger.post_transaction(
            actor=actor,
            chama_id=chama.id,
            source_type=PAYOUT_COMPLETION_SOURCE_TYPE,
            source_id=payout.id,
            description=f"Payout {payout.id} completion",
            lines=[
                LedgerLine(
                    account_id=get_account_id(self.db, chama.id, SHARE_CAPITAL_CODE),
                    debit=payout.amount,
                ),
                LedgerLine(
                    account_id=get_account_id(self.db, chama.id, CASH_CODE),
                    credit=payout.amount,
                ),
            ],
        )
        self.audit.record(
            actor=actor,
            chama_id=chama.id,
            action=AuditAction.PAYOUT_COMPLETE,
            resource_type="payout",
            resource_id=payout.id,
            payload={"amount": str(payout.amount)},
        )
        self.db.commit()
        return payout

    def fail(
        self,
        *,
        actor: User,
        chama_id: uuid.UUID,
        payout_id: uuid.UUID,
        failure_reason: str,
    ) -> Payout:
        chama = get_chama_or_404(self.db, chama_id)
        actor_membership = authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        require_roles(actor_membership, (RoleName.CHAIRPERSON, RoleName.TREASURER))
        payout = self._get_chama_payout(chama.id, payout_id)
        self._transition(payout, (PayoutStatus.PROCESSING,), PayoutStatus.FAILED)
        payout.failure_reason = failure_reason
        self.audit.record(
            actor=actor,
            chama_id=chama.id,
            action=AuditAction.PAYOUT_FAIL,
            resource_type="payout",
            resource_id=payout.id,
            payload={"failure_reason": failure_reason},
        )
        self.db.commit()
        return payout

    def reverse(self, *, actor: User, chama_id: uuid.UUID, payout_id: uuid.UUID) -> Payout:
        """Reverse a COMPLETED payout with a compensating ledger entry."""
        chama = get_chama_or_404(self.db, chama_id)
        actor_membership = authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        require_role(actor_membership, RoleName.CHAIRPERSON)
        payout = self._get_chama_payout(chama.id, payout_id)
        if payout.status != PayoutStatus.COMPLETED:
            raise StateError("Only a COMPLETED payout can be reversed")

        posting = self.ledger_repo.get_by_source(PAYOUT_COMPLETION_SOURCE_TYPE, payout.id)
        if posting is not None:
            self.ledger.reverse_transaction(
                actor=actor,
                chama_id=chama.id,
                transaction_id=posting.id,
                description=f"Payout {payout.id} reversal",
            )
        payout.status = PayoutStatus.REVERSED
        self.audit.record(
            actor=actor,
            chama_id=chama.id,
            action=AuditAction.PAYOUT_REVERSAL,
            resource_type="payout",
            resource_id=payout.id,
            payload={"amount": str(payout.amount)},
        )
        self.db.commit()
        return payout

    def list_by_chama(self, *, actor: User, chama_id: uuid.UUID) -> list[Payout]:
        chama = get_chama_or_404(self.db, chama_id)
        authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        return self.payouts.list_by_chama(chama.id)

    def _available_share_value(self, membership_id: uuid.UUID) -> Decimal:
        return member_share_value(self.db, membership_id) - self.payouts.completed_total_for_membership(
            membership_id
        )

    def _get_chama_payout(self, chama_id: uuid.UUID, payout_id: uuid.UUID) -> Payout:
        payout = self.payouts.get_by_id(payout_id)
        if payout is None or payout.chama_id != chama_id:
            raise NotFoundError("Payout not found in this Chama")
        return payout

    def _forbid_self_action(self, payout: Payout, actor_membership_id: uuid.UUID, verb: str) -> None:
        if payout.membership_id == actor_membership_id:
            raise StateError(f"A member cannot {verb} their own payout request")

    def _transition(self, payout: Payout, allowed_from: tuple[PayoutStatus, ...], to: PayoutStatus) -> None:
        if payout.status not in allowed_from:
            names = ", ".join(s.value for s in allowed_from)
            raise StateError(f"A payout in status {payout.status.value} cannot transition to {to.value}")
        payout.status = to
        self.db.flush()