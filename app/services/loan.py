"""Loan and loan-repayment service (ADR-020).

Implements the controlled loan lifecycle, eligibility rules (D-01), flat
interest and monthly term (D-02), interest-first repayment allocation and
overpayment rejection (D-03), and atomic, idempotent ledger postings for
disbursement and repayment.
"""

import calendar
import uuid
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, StateError
from app.models.enums import LoanRepaymentStatus, LoanStatus, MembershipStatus, RoleName
from app.models.loan import Loan
from app.models.user import User
from app.repositories.loan import LoanRepository
from app.repositories.loan_repayment import LoanRepaymentRepository
from app.repositories.ledger import LedgerRepository
from app.schemas.loan import LoanApplyRequest
from app.services.access import (
    authorize_chama_access,
    get_chama_or_404,
    get_target_membership,
    require_role,
    require_roles,
)
from app.services.audit import AuditAction, AuditService
from app.services.finance import available_chama_cash, get_account_id, member_share_value
from app.services.ledger import (
    CASH_CODE,
    INTEREST_INCOME_CODE,
    LOAN_DISBURSEMENT_SOURCE_TYPE,
    LOAN_REPAYMENT_SOURCE_TYPE,
    LOANS_RECEIVABLE_CODE,
    LedgerLine,
    LedgerService,
)

LOAN_INTEREST_RATE = Decimal("0.05")
MIN_TERM_MONTHS = 3
MAX_TERM_MONTHS = 12
MIN_TENURE_DAYS = 30


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _add_months(value: datetime, months: int) -> datetime:
    """Return *value* advanced by a whole number of calendar months."""
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


class LoanService:
    def __init__(self, db: Session):
        self.db = db
        self.loans = LoanRepository(db)
        self.repayments = LoanRepaymentRepository(db)
        self.ledger = LedgerService(db)
        self.ledger_repo = LedgerRepository(db)
        self.audit = AuditService(db)

    # --- lifecycle --------------------------------------------------------

    def apply(self, *, actor: User, chama_id: uuid.UUID, data: LoanApplyRequest) -> Loan:
        chama = get_chama_or_404(self.db, chama_id)
        membership = authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        principal = data.principal
        if _as_aware_utc(membership.joined_at) > datetime.now(timezone.utc) - timedelta(
            days=MIN_TENURE_DAYS
        ):
            raise StateError(
                "A member must have been an active member for at least one month to apply"
            )
        self._check_principal_limit(membership.id, chama.id, principal)

        loan = Loan(
            chama_id=chama.id,
            membership_id=membership.id,
            principal=principal,
            interest_rate=LOAN_INTEREST_RATE,
            term_months=data.term_months,
            status=LoanStatus.DRAFT,
            recorded_by_user_id=actor.id,
            note=data.note,
        )
        self.db.add(loan)
        self.db.flush()
        self.audit.record(
            actor=actor,
            chama_id=chama.id,
            action=AuditAction.LOAN_APPLY,
            resource_type="loan",
            resource_id=loan.id,
            payload={"principal": str(principal), "term_months": data.term_months},
        )
        self.db.commit()
        return loan

    def submit(self, *, actor: User, chama_id: uuid.UUID, loan_id: uuid.UUID) -> Loan:
        chama = get_chama_or_404(self.db, chama_id)
        membership = authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        loan = self._get_chama_loan(chama.id, loan_id)
        if loan.membership_id != membership.id:
            raise StateError("Only the applicant can submit their loan application")
        self._transition(loan, (LoanStatus.DRAFT,), LoanStatus.SUBMITTED)
        self.audit.record(
            actor=actor,
            chama_id=chama.id,
            action=AuditAction.LOAN_SUBMIT,
            resource_type="loan",
            resource_id=loan.id,
        )
        self.db.commit()
        return loan

    def approve(self, *, actor: User, chama_id: uuid.UUID, loan_id: uuid.UUID) -> Loan:
        chama = get_chama_or_404(self.db, chama_id)
        actor_membership = authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        require_role(actor_membership, RoleName.CHAIRPERSON)
        loan = self._get_chama_loan(chama.id, loan_id)
        self._forbid_self_action(loan, actor_membership.id, "approve")
        self._transition(loan, (LoanStatus.SUBMITTED,), LoanStatus.APPROVED)
        loan.approval_date = datetime.now()
        loan.approved_by_user_id = actor.id
        self.audit.record(
            actor=actor,
            chama_id=chama.id,
            action=AuditAction.LOAN_APPROVE,
            resource_type="loan",
            resource_id=loan.id,
        )
        self.db.commit()
        return loan

    def reject(self, *, actor: User, chama_id: uuid.UUID, loan_id: uuid.UUID, note: str | None) -> Loan:
        chama = get_chama_or_404(self.db, chama_id)
        actor_membership = authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        require_role(actor_membership, RoleName.CHAIRPERSON)
        loan = self._get_chama_loan(chama.id, loan_id)
        self._forbid_self_action(loan, actor_membership.id, "reject")
        self._transition(loan, (LoanStatus.SUBMITTED,), LoanStatus.REJECTED)
        self.audit.record(
            actor=actor,
            chama_id=chama.id,
            action=AuditAction.LOAN_REJECT,
            resource_type="loan",
            resource_id=loan.id,
            payload={"note": note},
        )
        self.db.commit()
        return loan

    def cancel(self, *, actor: User, chama_id: uuid.UUID, loan_id: uuid.UUID) -> Loan:
        chama = get_chama_or_404(self.db, chama_id)
        actor_membership = authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        require_role(actor_membership, RoleName.CHAIRPERSON)
        loan = self._get_chama_loan(chama.id, loan_id)
        self._transition(loan, (LoanStatus.APPROVED,), LoanStatus.CANCELLED)
        self.audit.record(
            actor=actor,
            chama_id=chama.id,
            action=AuditAction.LOAN_CANCEL,
            resource_type="loan",
            resource_id=loan.id,
        )
        self.db.commit()
        return loan

    def disburse(self, *, actor: User, chama_id: uuid.UUID, loan_id: uuid.UUID) -> Loan:
        """Disburse an APPROVED loan atomically with its ledger posting.

        Idempotent: a retry after success returns the DISBURSED loan without a
        second financial effect. A loan can never be DISBURSED without its
        ledger transaction or posted without changing state, because both
        happen in one transaction.
        """
        chama = get_chama_or_404(self.db, chama_id)
        actor_membership = authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        require_role(actor_membership, RoleName.CHAIRPERSON)
        loan = self._get_chama_loan(chama.id, loan_id)

        posting = self.ledger_repo.get_by_source(LOAN_DISBURSEMENT_SOURCE_TYPE, loan.id)
        if loan.status == LoanStatus.DISBURSED:
            if posting is None:
                raise StateError("Disbursed loan is missing its ledger transaction")
            return loan

        self._transition(loan, (LoanStatus.APPROVED,), LoanStatus.DISBURSED)
        cash = available_chama_cash(self.db, chama.id)
        if loan.principal > cash:
            raise StateError("Insufficient available Chama cash to disburse this loan")
        loan.disbursement_date = datetime.now()
        loan.maturity_date = _add_months(loan.disbursement_date, loan.term_months)
        loan.disbursed_by_user_id = actor.id

        self.ledger.post_transaction(
            actor=actor,
            chama_id=chama.id,
            source_type=LOAN_DISBURSEMENT_SOURCE_TYPE,
            source_id=loan.id,
            description=f"Loan {loan.id} disbursement",
            lines=[
                LedgerLine(
                    account_id=get_account_id(self.db, chama.id, LOANS_RECEIVABLE_CODE),
                    debit=loan.principal,
                ),
                LedgerLine(
                    account_id=get_account_id(self.db, chama.id, CASH_CODE),
                    credit=loan.principal,
                ),
            ],
        )
        self.audit.record(
            actor=actor,
            chama_id=chama.id,
            action=AuditAction.LOAN_DISBURSE,
            resource_type="loan",
            resource_id=loan.id,
            payload={"principal": str(loan.principal)},
        )
        self.db.commit()
        return loan

    def _transition(self, loan: Loan, allowed_from: tuple[LoanStatus, ...], to: LoanStatus) -> None:
        if loan.status not in allowed_from:
            names = ", ".join(s.value for s in allowed_from)
            raise StateError(f"A loan in status {loan.status.value} cannot transition to {to.value}")
        loan.status = to
        self.db.flush()

    def _forbid_self_action(self, loan: Loan, actor_membership_id: uuid.UUID, verb: str) -> None:
        if loan.membership_id == actor_membership_id:
            raise StateError(f"A member cannot {verb} their own loan application")

    def _get_chama_loan(self, chama_id: uuid.UUID, loan_id: uuid.UUID) -> Loan:
        loan = self.loans.get_by_id(loan_id)
        if loan is None or loan.chama_id != chama_id:
            raise NotFoundError("Loan not found in this Chama")
        return loan

    # --- repayments -------------------------------------------------------

    def record_repayment(
        self, *, actor: User, chama_id: uuid.UUID, loan_id: uuid.UUID, amount: Decimal, note: str | None
    ) -> Loan:
        chama = get_chama_or_404(self.db, chama_id)
        actor_membership = authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        require_roles(actor_membership, (RoleName.CHAIRPERSON, RoleName.TREASURER))
        loan = self._get_chama_loan(chama.id, loan_id)
        if loan.status not in (LoanStatus.DISBURSED, LoanStatus.PARTIALLY_REPAID):
            raise StateError("Only a disbursed loan can receive repayments")

        outstanding_principal, outstanding_interest = self.outstanding_for(loan)
        owed = outstanding_principal + outstanding_interest
        if amount > owed:
            raise StateError("Repayment exceeds the loan's outstanding balance")

        interest_portion = min(amount, outstanding_interest)
        principal_portion = amount - interest_portion
        repayment = self.repayments.create(
            chama_id=chama.id,
            loan_id=loan.id,
            amount=amount,
            principal_portion=principal_portion,
            interest_portion=interest_portion,
            recorded_by_user_id=actor.id,
            note=note,
        )
        loan.status = self._status_from_outstanding(
            loan, outstanding_principal - principal_portion, outstanding_interest - interest_portion
        )
        self.db.flush()

        lines = [
            LedgerLine(account_id=get_account_id(self.db, chama.id, CASH_CODE), debit=amount)
        ]
        if principal_portion > 0:
            lines.append(
                LedgerLine(
                    account_id=get_account_id(self.db, chama.id, LOANS_RECEIVABLE_CODE),
                    credit=principal_portion,
                )
            )
        if interest_portion > 0:
            lines.append(
                LedgerLine(
                    account_id=get_account_id(self.db, chama.id, INTEREST_INCOME_CODE),
                    credit=interest_portion,
                )
            )
        self.ledger.post_transaction(
            actor=actor,
            chama_id=chama.id,
            source_type=LOAN_REPAYMENT_SOURCE_TYPE,
            source_id=repayment.id,
            description=f"Loan {loan.id} repayment",
            lines=lines,
        )
        self.audit.record(
            actor=actor,
            chama_id=chama.id,
            action=AuditAction.LOAN_REPAYMENT,
            resource_type="loan_repayment",
            resource_id=repayment.id,
            payload={
                "loan_id": str(loan.id),
                "principal_portion": str(principal_portion),
                "interest_portion": str(interest_portion),
            },
        )
        self.db.commit()
        return loan

    def reverse_repayment(
        self,
        *,
        actor: User,
        chama_id: uuid.UUID,
        loan_id: uuid.UUID,
        repayment_id: uuid.UUID,
        note: str | None,
    ) -> Loan:
        chama = get_chama_or_404(self.db, chama_id)
        actor_membership = authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        require_role(actor_membership, RoleName.CHAIRPERSON)
        loan = self._get_chama_loan(chama.id, loan_id)
        repayment = self.repayments.get_by_id(repayment_id)
        if repayment is None or repayment.loan_id != loan.id or repayment.chama_id != chama.id:
            raise NotFoundError("Repayment not found for this loan in this Chama")
        if repayment.status != LoanRepaymentStatus.CONFIRMED:
            raise StateError("Only a confirmed repayment can be reversed")

        posting = self.ledger_repo.get_by_source(LOAN_REPAYMENT_SOURCE_TYPE, repayment.id)
        if posting is not None:
            self.ledger.reverse_transaction(
                actor=actor,
                chama_id=chama.id,
                transaction_id=posting.id,
                description=f"Loan {loan.id} repayment reversal",
            )
        repayment.status = LoanRepaymentStatus.REVERSED
        loan.status = self._status_after_reversal(loan)
        self.audit.record(
            actor=actor,
            chama_id=chama.id,
            action=AuditAction.LOAN_REPAYMENT_REVERSAL,
            resource_type="loan_repayment",
            resource_id=repayment.id,
            payload={"loan_id": str(loan.id), "note": note},
        )
        self.db.commit()
        return loan

    # --- reads ------------------------------------------------------------

    def list_by_chama(self, *, actor: User, chama_id: uuid.UUID) -> list[Loan]:
        chama = get_chama_or_404(self.db, chama_id)
        authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        return self.loans.list_by_chama(chama.id)

    def list_by_membership(
        self, *, actor: User, chama_id: uuid.UUID, membership_id: uuid.UUID
    ) -> list[Loan]:
        chama = get_chama_or_404(self.db, chama_id)
        authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        membership = get_target_membership(self.db, chama_id=chama.id, membership_id=membership_id)
        return self.loans.list_by_membership(membership.id)

    def list_repayments(
        self, *, actor: User, chama_id: uuid.UUID, loan_id: uuid.UUID
    ) -> list[object]:
        chama = get_chama_or_404(self.db, chama_id)
        authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        loan = self._get_chama_loan(chama.id, loan_id)
        return self.repayments.list_by_loan(loan.id)

    # --- derived values ---------------------------------------------------

    def interest_for(self, loan: Loan) -> Decimal:
        return (loan.principal * loan.interest_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def outstanding_for(self, loan: Loan) -> tuple[Decimal, Decimal]:
        """Return ``(outstanding_principal, outstanding_interest)`` derived on read."""
        paid_principal = Decimal("0")
        paid_interest = Decimal("0")
        for repayment in self.repayments.confirmed_by_loan(loan.id):
            paid_principal += repayment.principal_portion
            paid_interest += repayment.interest_portion
        outstanding_principal = (loan.principal - paid_principal).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        outstanding_interest = (self.interest_for(loan) - paid_interest).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return outstanding_principal, outstanding_interest

    def _status_from_outstanding(
        self, loan: Loan, outstanding_principal: Decimal, outstanding_interest: Decimal
    ) -> LoanStatus:
        if outstanding_principal <= 0 and outstanding_interest <= 0:
            return LoanStatus.REPAID
        if outstanding_principal == loan.principal and outstanding_interest == self.interest_for(loan):
            return LoanStatus.DISBURSED
        return LoanStatus.PARTIALLY_REPAID

    def _status_after_reversal(self, loan: Loan) -> LoanStatus:
        confirmed = self.repayments.confirmed_by_loan(loan.id)
        paid_principal = sum((r.principal_portion for r in confirmed), Decimal("0"))
        paid_interest = sum((r.interest_portion for r in confirmed), Decimal("0"))
        return self._status_from_outstanding(
            loan, loan.principal - paid_principal, self.interest_for(loan) - paid_interest
        )

    def is_overdue(self, loan: Loan) -> bool:
        if loan.status not in (LoanStatus.DISBURSED, LoanStatus.PARTIALLY_REPAID):
            return False
        if loan.maturity_date is None:
            return False
        return _as_aware_utc(loan.maturity_date) < datetime.now(timezone.utc)

    def serialize(self, loan: Loan) -> dict:
        principal, interest = self.outstanding_for(loan)
        total_interest = self.interest_for(loan)
        return {
            "id": loan.id,
            "chama_id": loan.chama_id,
            "membership_id": loan.membership_id,
            "principal": loan.principal,
            "interest_rate": loan.interest_rate,
            "term_months": loan.term_months,
            "total_interest": total_interest,
            "total_expected_repayment": loan.principal + total_interest,
            "outstanding_principal": principal,
            "outstanding_interest": interest,
            "status": loan.status.value,
            "is_overdue": self.is_overdue(loan),
            "application_date": loan.application_date,
            "approval_date": loan.approval_date,
            "disbursement_date": loan.disbursement_date,
            "maturity_date": loan.maturity_date,
            "approved_by_user_id": loan.approved_by_user_id,
            "disbursed_by_user_id": loan.disbursed_by_user_id,
            "recorded_by_user_id": loan.recorded_by_user_id,
            "note": loan.note,
            "created_at": loan.created_at,
            "updated_at": loan.updated_at,
        }

    # --- eligibility ------------------------------------------------------

    def _check_principal_limit(self, membership_id: uuid.UUID, chama_id: uuid.UUID, principal: Decimal) -> None:
        share_value = member_share_value(self.db, membership_id)
        if principal > share_value * 3:
            raise StateError("Loan principal cannot exceed three times the member's share value")
        cash = available_chama_cash(self.db, chama_id)
        if principal > cash:
            raise StateError("Loan principal cannot exceed the Chama's available cash")