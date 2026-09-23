"""Append-only business audit event service (ADR-023).

Records who performed an action, when, against what resource, and from which
request. The audit system is separate from the ledger: it never stores
financial balances or secrets, and events are immutable at the database level.
"""

import uuid

from sqlalchemy.orm import Session

from app.core.logging import get_request_id
from app.models.audit_event import AuditEvent
from app.models.user import User
from app.repositories.audit import AuditRepository
from app.services.access import authorize_chama_access, get_chama_or_404


class AuditAction:
    # Authentication
    AUTH_REGISTER = "auth.register"
    AUTH_LOGIN = "auth.login"
    AUTH_LOGIN_FAILED = "auth.login_failed"
    AUTH_LOGOUT = "auth.logout"
    AUTH_REFRESH = "auth.refresh"
    AUTH_MEMBER_LINK = "auth.member_link"
    # Administrative
    CHAMA_CREATE = "chama.create"
    CHAMA_UPDATE = "chama.update"
    CHAMA_STATUS_CHANGE = "chama.status_change"
    # Membership
    MEMBERSHIP_CREATE = "membership.create"
    MEMBERSHIP_STATUS_CHANGE = "membership.status_change"
    # Roles
    ROLE_ASSIGN = "role.assign"
    ROLE_REMOVE = "role.remove"
    # Contributions
    CONTRIBUTION_CREATE = "contribution.create"
    CONTRIBUTION_CONFIRM = "contribution.confirm"
    CONTRIBUTION_REVERSE = "contribution.reverse"
    # Registration fees
    FEE_PAY = "registration_fee.pay"
    FEE_PAY_REVERSAL = "registration_fee.pay_reversal"
    FEE_WAIVE = "registration_fee.waive"
    # Loans
    LOAN_APPLY = "loan.apply"
    LOAN_SUBMIT = "loan.submit"
    LOAN_APPROVE = "loan.approve"
    LOAN_REJECT = "loan.reject"
    LOAN_CANCEL = "loan.cancel"
    LOAN_DISBURSE = "loan.disburse"
    LOAN_REPAYMENT = "loan.repayment"
    LOAN_REPAYMENT_REVERSAL = "loan.repayment_reversal"
    # Payouts
    PAYOUT_REQUEST = "payout.request"
    PAYOUT_APPROVE = "payout.approve"
    PAYOUT_REJECT = "payout.reject"
    PAYOUT_PROCESS = "payout.process"
    PAYOUT_COMPLETE = "payout.complete"
    PAYOUT_FAIL = "payout.fail"
    PAYOUT_REVERSAL = "payout.reversal"
    # Payment configuration
    PAYMENT_CONNECTION_CREATED = "payment_connection.created"
    PAYMENT_CONNECTION_VALIDATED = "payment_connection.validated"
    PAYMENT_CONNECTION_ENABLED = "payment_connection.enabled"
    PAYMENT_CONNECTION_DISABLED = "payment_connection.disabled"
    PAYMENT_CONNECTION_CREDENTIALS_REPLACED = "payment_connection.credentials_replaced"
    C2B_REGISTRATION = "c2b.registration"


class AuditService:
    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditRepository(db)

    def record(
        self,
        *,
        actor: User | None,
        chama_id: uuid.UUID | None,
        action: str,
        resource_type: str,
        resource_id: uuid.UUID | None = None,
        payload: dict | None = None,
        success: bool = True,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditEvent:
        """Record an event in the caller's transaction (caller commits)."""
        event = self.audit.create(
            chama_id=chama_id,
            actor_user_id=actor.id if actor is not None else None,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=get_request_id(),
            payload=payload,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.flush()
        return event

    def record_commit(
        self,
        *,
        actor: User | None,
        chama_id: uuid.UUID | None,
        action: str,
        resource_type: str,
        resource_id: uuid.UUID | None = None,
        payload: dict | None = None,
        success: bool = True,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditEvent:
        """Record an event in its own transaction and commit.

        Used where the audited action did not create financial records (e.g.
        failed logins), so the event must survive independently.
        """
        event = self.record(
            actor=actor,
            chama_id=chama_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            payload=payload,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.commit()
        return event

    def list_for_chama(self, *, actor: User, chama_id: uuid.UUID) -> list[AuditEvent]:
        """Return the Chama's audit events (any active member may read)."""
        chama = get_chama_or_404(self.db, chama_id)
        authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        return self.audit.list_by_chama(chama.id)