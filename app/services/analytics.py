"""Role-scoped, ledger-backed Chama collection analytics."""

from datetime import datetime, timezone
from decimal import Decimal
import uuid

from sqlalchemy import and_, case, extract, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.models.contribution import Contribution
from app.models.ledger_account import LedgerAccount
from app.models.ledger_entry import LedgerEntry
from app.models.ledger_transaction import LedgerTransaction
from app.models.registration_fee_payment import RegistrationFeePayment
from app.models.user import User
from app.schemas.analytics import CollectionAnalyticsMonth, CollectionAnalyticsOut
from app.services.access import LEADERSHIP_ROLES, authorize_chama_access, get_chama_or_404
from app.services.ledger import (
    CASH_CODE,
    CONTRIBUTION_SOURCE_TYPE,
    REGISTRATION_FEE_PAYMENT_SOURCE_TYPE,
    REVERSAL_SOURCE_TYPE,
)


class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db

    def collections(
        self, *, actor: User, chama_id: uuid.UUID
    ) -> CollectionAnalyticsOut:
        chama = get_chama_or_404(self.db, chama_id)
        membership = authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        group_scope = any(membership.has_role(role) for role in LEADERSHIP_ROLES)
        membership_id = None if group_scope else membership.id

        end = datetime.now(timezone.utc).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        start = _month_offset(end, -11)
        totals: dict[tuple[int, int], dict[str, Decimal]] = {}
        for category, source_type, source_model in (
            ("contributions", CONTRIBUTION_SOURCE_TYPE, Contribution),
            ("registration_fees", REGISTRATION_FEE_PAYMENT_SOURCE_TYPE, RegistrationFeePayment),
        ):
            for year, month, amount in self._monthly_cash_flow(
                chama_id=chama.id,
                start=start,
                end=_month_offset(end, 1),
                source_type=source_type,
                source_model=source_model,
                membership_id=membership_id,
            ):
                totals.setdefault((year, month), {})[category] = amount

        months: list[CollectionAnalyticsMonth] = []
        for offset in range(-11, 1):
            month_start = _month_offset(end, offset)
            values = totals.get((month_start.year, month_start.month), {})
            contributions = values.get("contributions", Decimal("0.00"))
            fees = values.get("registration_fees", Decimal("0.00"))
            months.append(
                CollectionAnalyticsMonth(
                    month=month_start.strftime("%Y-%m"),
                    contributions=contributions,
                    registration_fees=fees,
                    total_collected=contributions + fees,
                )
            )

        return CollectionAnalyticsOut(
            scope="group" if group_scope else "member",
            months=months,
        )

    def _monthly_cash_flow(
        self,
        *,
        chama_id: uuid.UUID,
        start: datetime,
        end: datetime,
        source_type: str,
        source_model,
        membership_id: uuid.UUID | None,
    ) -> list[tuple[int, int, Decimal]]:
        original = aliased(LedgerTransaction)
        transaction = LedgerTransaction
        cash_flow = func.sum(LedgerEntry.debit - LedgerEntry.credit)
        year_expr = extract("year", transaction.created_at)
        month_expr = extract("month", transaction.created_at)
        source_id = case(
            (transaction.source_type == REVERSAL_SOURCE_TYPE, original.source_id),
            else_=transaction.source_id,
        )
        stmt = (
            select(year_expr, month_expr, cash_flow)
            .select_from(transaction)
            .join(
                LedgerEntry,
                and_(
                    LedgerEntry.transaction_id == transaction.id,
                    LedgerEntry.chama_id == transaction.chama_id,
                ),
            )
            .join(
                LedgerAccount,
                and_(
                    LedgerAccount.id == LedgerEntry.account_id,
                    LedgerAccount.chama_id == LedgerEntry.chama_id,
                ),
            )
            .outerjoin(original, transaction.reverses_transaction_id == original.id)
            .where(
                transaction.chama_id == chama_id,
                transaction.created_at >= start,
                transaction.created_at < end,
                LedgerAccount.code == CASH_CODE,
                or_(
                    transaction.source_type == source_type,
                    and_(
                        transaction.source_type == REVERSAL_SOURCE_TYPE,
                        original.source_type == source_type,
                    ),
                ),
            )
        )
        if membership_id is not None:
            stmt = stmt.join(source_model, source_model.id == source_id).where(
                source_model.membership_id == membership_id
            )
        stmt = stmt.group_by(year_expr, month_expr).order_by(year_expr, month_expr)
        return [
            (int(year), int(month), Decimal(amount or 0))
            for year, month, amount in self.db.execute(stmt)
        ]


def _month_offset(value: datetime, offset: int) -> datetime:
    month_index = value.year * 12 + value.month - 1 + offset
    year, month_index = divmod(month_index, 12)
    return value.replace(year=year, month=month_index + 1)
