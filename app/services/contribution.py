"""Contribution service."""

import uuid
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError, StateError
from app.db.bootstrap import system_user_id
from app.models.contribution import Contribution
from app.models.enums import ContributionStatus, RoleName, ShareStatus
from app.models.ledger_account import LedgerAccount
from app.models.user import User
from app.repositories.contribution import ContributionRepository
from app.repositories.ledger import LedgerRepository
from app.repositories.share import ShareRepository
from app.schemas.membership import ContributionCreate
from app.services.access import (
    authorize_chama_access,
    get_chama_or_404,
    get_target_membership,
    require_roles,
)
from app.services.ledger import (
    CASH_CODE,
    CONTRIBUTION_SOURCE_TYPE,
    SHARE_CAPITAL_CODE,
    LedgerLine,
    LedgerService,
)


class ContributionService:
    def __init__(self, db: Session):
        self.db = db
        self.contributions = ContributionRepository(db)
        self.shares = ShareRepository(db)
        self.ledger = LedgerService(db)
        self.ledger_repo = LedgerRepository(db)

    def record(self, *, actor: User, chama_id: uuid.UUID, data: ContributionCreate) -> Contribution:
        chama = get_chama_or_404(self.db, chama_id)
        actor_membership = authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        require_roles(actor_membership, (RoleName.CHAIRPERSON, RoleName.TREASURER))
        membership = get_target_membership(
            self.db, chama_id=chama.id, membership_id=data.membership_id
        )

        existing = self._find_open_contribution(membership.id, data.period)
        if existing is not None:
            raise ConflictError(
                "This membership already has a contribution for this period that has not been reversed"
            )

        contribution = self.contributions.create(
            membership_id=membership.id,
            amount=data.amount,
            period=data.period,
            recorded_by_user_id=actor.id,
            note=data.note,
        )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("Duplicate contribution for this membership and period") from exc
        return contribution

    def confirm(self, *, actor: User, chama_id: uuid.UUID, contribution_id: uuid.UUID) -> Contribution:
        chama = get_chama_or_404(self.db, chama_id)
        actor_membership = authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        require_roles(actor_membership, (RoleName.CHAIRPERSON,))
        contribution = self._get_chama_contribution(chama.id, contribution_id)
        return self._settle(contribution, actor, allow_already_confirmed=False)

    def _settle(self, contribution: Contribution, actor: User, *, allow_already_confirmed: bool) -> Contribution:
        """Confirm a PENDING contribution and post its immutable ledger entry.

        Used by the manual confirm endpoint (human actor) and by money-in
        settlement (system user). OQ-013: each confirmed contribution posts a
        single balanced transaction DR Cash / CR Share Capital, idempotent by
        ``CONTRIBUTION_CONFIRMATION:<contribution_id>``.
        """
        if contribution.status == ContributionStatus.CONFIRMED:
            if allow_already_confirmed:
                return contribution
            raise StateError("Only a PENDING contribution can be confirmed")
        if contribution.status != ContributionStatus.PENDING:
            raise StateError("Only a PENDING contribution can be confirmed")

        contribution.status = ContributionStatus.CONFIRMED
        contribution.confirmed_at = datetime.now()
        units = self._units_for(contribution.amount)
        self.shares.create(
            membership_id=contribution.membership_id,
            contribution_id=contribution.id,
            units=units,
        )
        self._post_confirmation(contribution, actor)
        self.db.commit()
        return contribution

    def _post_confirmation(self, contribution: Contribution, actor: User) -> None:
        chama_id = contribution.membership.chama_id
        self.ledger.post_transaction(
            actor=actor,
            chama_id=chama_id,
            source_type=CONTRIBUTION_SOURCE_TYPE,
            source_id=contribution.id,
            description=f"Contribution {contribution.period} confirmation",
            lines=[
                LedgerLine(account_id=self._account_id(chama_id, CASH_CODE), debit=contribution.amount),
                LedgerLine(account_id=self._account_id(chama_id, SHARE_CAPITAL_CODE), credit=contribution.amount),
            ],
            require_membership=actor.id != system_user_id(),
        )

    def _account_id(self, chama_id: uuid.UUID, code: str) -> uuid.UUID:
        account = self.db.scalars(
            select(LedgerAccount).where(
                LedgerAccount.chama_id == chama_id, LedgerAccount.code == code
            )
        ).first()
        if account is None:
            raise StateError(f"The default ledger account {code} is missing for this Chama")
        return account.id

    def reverse(
        self,
        *,
        actor: User,
        chama_id: uuid.UUID,
        contribution_id: uuid.UUID,
        note: str | None,
    ) -> Contribution:
        chama = get_chama_or_404(self.db, chama_id)
        actor_membership = authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        require_roles(actor_membership, (RoleName.CHAIRPERSON,))
        contribution = self._get_chama_contribution(chama.id, contribution_id)

        if contribution.status != ContributionStatus.CONFIRMED:
            raise StateError("Only a CONFIRMED contribution can be reversed")

        contribution.status = ContributionStatus.REVERSED
        if note is not None:
            contribution.note = note
        for share in contribution.shares:
            share.status = ShareStatus.REVERSED
        posting = self.ledger_repo.get_by_source(CONTRIBUTION_SOURCE_TYPE, contribution.id)
        if posting is not None:
            self.ledger.reverse_transaction(
                actor=actor,
                chama_id=chama.id,
                transaction_id=posting.id,
                description=f"Contribution {contribution.period} reversal",
            )
        else:
            self.db.commit()
        return contribution

    def list_by_chama(self, *, actor: User, chama_id: uuid.UUID) -> list[Contribution]:
        chama = get_chama_or_404(self.db, chama_id)
        authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        return self.contributions.list_by_chama(chama.id)

    def _find_open_contribution(self, membership_id: uuid.UUID, period: str) -> Contribution | None:
        stmt = select(Contribution).where(
            Contribution.membership_id == membership_id,
            Contribution.period == period,
            Contribution.status != ContributionStatus.REVERSED,
        )
        return self.db.scalars(stmt).first()

    def _get_chama_contribution(self, chama_id: uuid.UUID, contribution_id: uuid.UUID) -> Contribution:
        contribution = self.contributions.get_by_id(contribution_id)
        if contribution is None or contribution.membership.chama_id != chama_id:
            raise NotFoundError("Contribution not found in this Chama")
        return contribution

    def _units_for(self, amount: Decimal) -> Decimal:
        unit_price = get_settings().share_unit_price
        return (amount / unit_price).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)