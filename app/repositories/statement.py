"""Read-only aggregation queries backing PDF statements.

Statements are projections: they never write financial state. Every figure is
derived from the authoritative records (contributions, shares, registration
fees, loans, payouts and ledger entries) inside the requested window.
"""

import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.models.contribution import Contribution
from app.models.enums import ContributionStatus, ShareStatus
from app.models.ledger_entry import LedgerEntry
from app.models.ledger_transaction import LedgerTransaction
from app.models.share import Share


def _as_date(value: date | datetime | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


class StatementRepository:
    """Window-limited aggregation queries.

    Timestamps are compared against a half-open interval ``[from, to_exclusive)``
    so that a request for ``to=2026-01-31`` includes the whole of that day.
    On SQLite the stored text format is normalised with ``strftime`` so the
    comparison matches what ``CURRENT_TIMESTAMP`` writes; PostgreSQL compares
    native timestamps directly.
    """

    def __init__(self, db: Session):
        self.db = db
        self.is_sqlite = inspect(db.get_bind()).dialect.name == "sqlite"

    def _window(self, stmt, column, start: datetime, end: datetime):
        if self.is_sqlite:
            col = func.strftime("%Y-%m-%d %H:%M:%S", column)
            return stmt.where(
                col >= start.strftime("%Y-%m-%d %H:%M:%S"),
                col < end.strftime("%Y-%m-%d %H:%M:%S"),
            )
        return stmt.where(column >= start, column < end)

    def contributions_in_window(
        self,
        *,
        chama_id: uuid.UUID,
        start: datetime,
        end: datetime,
        membership_ids: list[uuid.UUID] | None,
    ) -> list[tuple[Contribution, Decimal]]:
        """Confirmed, non-reversed contributions with their total share units.

        Only ``CONFIRMED`` contributions are included: pending rows are not
        financial facts and reversed rows have already been unwound by a
        compensating ledger transaction.
        """
        stmt = (
            select(Contribution, Share.units)
            .join(Contribution.membership)
            .outerjoin(Share, Share.contribution_id == Contribution.id)
            .where(
                Contribution.membership.has(chama_id=chama_id),
                Contribution.status == ContributionStatus.CONFIRMED,
            )
        )
        if membership_ids is not None:
            stmt = stmt.where(Contribution.membership_id.in_(membership_ids))
        stmt = self._window(stmt, Contribution.confirmed_at, start, end)
        rows = self.db.execute(stmt).all()
        return [
            (contribution, Decimal(units or 0).quantize(Decimal("0.0001")))
            for contribution, units in rows
        ]

    def ledger_entries_in_window(
        self,
        *,
        chama_id: uuid.UUID,
        start: datetime,
        end: datetime,
    ) -> list[tuple[LedgerTransaction, LedgerEntry]]:
        """Ledger lines posted inside the window, oldest first.

        Chama-wide statements show the whole ledger; member statements are
        narrowed to the accounts that represent member balances so that
        member statements never leak another member's postings.
        """
        stmt = (
            select(LedgerTransaction, LedgerEntry)
            .join(LedgerEntry, LedgerEntry.transaction_id == LedgerTransaction.id)
            .where(LedgerTransaction.chama_id == chama_id)
        )
        stmt = self._window(stmt, LedgerTransaction.created_at, start, end)
        stmt = stmt.order_by(LedgerTransaction.created_at, LedgerTransaction.id, LedgerEntry.id)
        rows = self.db.execute(stmt).all()
        results = []
        for transaction, entry in rows:
            account_code = entry.account.code if hasattr(entry, "account") and entry.account is not None else None
            if account_code is None:
                account_code = entry.account_code if hasattr(entry, "account_code") else None
            results.append((transaction, entry, str(account_code) if account_code is not None else ""))
        self.db.expunge_all()
        return results

    def shares_in_window(
        self,
        *,
        chama_id: uuid.UUID,
        start: datetime,
        end: datetime,
        membership_ids: list[uuid.UUID] | None,
    ) -> list[Share]:
        stmt = select(Share).join(Share.membership).where(
            Share.membership.has(chama_id=chama_id),
            Share.status == ShareStatus.ACTIVE,
        )
        if membership_ids is not None:
            stmt = stmt.where(Share.membership_id.in_(membership_ids))
        stmt = self._window(stmt, Share.created_at, start, end)
        return list(self.db.scalars(stmt.order_by(Share.created_at, Share.id)))

    @staticmethod
    def window_bounds(
        *, date_from: date | None, date_to: date | None
    ) -> tuple[datetime, datetime, date, date]:
        """Resolve the inclusive date range into a half-open UTC-ish interval."""
        start_day = date_from or date(1970, 1, 1)
        end_day = date_to or date.today()
        if end_day < start_day:
            from app.core.errors import AppError

            raise AppError("'to' must be on or after 'from'")
        start = datetime.combine(start_day, time.min)
        end = datetime.combine(end_day, time.max) + (datetime.resolution)
        return start, end, start_day, end_day
