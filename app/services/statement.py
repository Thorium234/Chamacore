"""Statement assembly.

Aggregates authoritative records into a plain-data structure, then renders it
as a PDF. No financial state is written: a statement is a read-only projection.

Authorization follows the documented rule (docs/15_STRATEGIC_PLAN.md W6):

- CHAIRPERSON / TREASURER may request a Chama-wide statement.
- Any other active member may only request their own statement.
- A PLATFORM_ADMIN with no membership in the Chama may request a Chama-wide
  statement because their oversight grant is global.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.errors import PermissionDeniedError
from app.models.chama import Chama
from app.models.enums import RoleName
from app.models.membership import Membership
from app.models.user import User
from app.repositories.statement import StatementRepository
from app.services.access import (
    authorize_chama_access,
    get_chama_or_404,
    get_target_membership,
    is_platform_admin,
)

# Roles permitted to read every member's figures in the Chama.
CHAMA_WIDE_ROLES = (RoleName.CHAIRPERSON, RoleName.TREASURER)

CURRENCY = "KES"

# Ledger accounts disclosed on a plain-member statement: share capital and
# registration fees. Income, expense, liability and payout accounts remain
# executive-only.
MEMBER_STATEMENT_ACCOUNT_CODES = frozenset({"3000", "4000"})


@dataclass(frozen=True)
class StatementLine:
    posted_on: date | None
    reference: str
    description: str
    debit: Decimal
    credit: Decimal
    running_balance: Decimal


@dataclass(frozen=True)
class ContributionLine:
    period: str
    amount: Decimal
    paid_on: date | None
    share_units: Decimal


@dataclass(frozen=True)
class Statement:
    chama_name: str
    chama_status: str
    scope_label: str
    member_name: str | None
    member_number: int | None
    period_from: date
    period_to: date
    generated_at: str
    currency: str = CURRENCY
    contributions: list[ContributionLine] = field(default_factory=list)
    lines: list[StatementLine] = field(default_factory=list)
    total_debit: Decimal = Decimal("0.00")
    total_credit: Decimal = Decimal("0.00")
    closing_balance: Decimal = Decimal("0.00")


class StatementService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = StatementRepository(db)

    def build(
        self,
        *,
        actor: User,
        chama_id: uuid.UUID,
        date_from: date | None,
        date_to: date | None,
        membership_id: uuid.UUID | None,
    ) -> Statement:
        chama = get_chama_or_404(self.db, chama_id)
        membership, scope_ids, scope_label, member_label = self._resolve_scope(
            actor=actor, chama=chama, membership_id=membership_id
        )
        start, end, from_day, to_day = self.repository.window_bounds(
            date_from=date_from, date_to=date_to
        )

        contributions = [
            ContributionLine(
                period=contribution.period,
                amount=Decimal(contribution.amount).quantize(Decimal("0.01")),
                paid_on=contribution.payment_date,
                share_units=units,
            )
            for contribution, units in self.repository.contributions_in_window(
                chama_id=chama.id,
                start=start,
                end=end,
                membership_ids=scope_ids,
            )
        ]

        # Chama-wide statements include every ledger line. A member statement is
        # restricted to the member-facing accounts so no other member's postings
        # are disclosed.
        ledger = self.repository.ledger_entries_in_window(
            chama_id=chama.id, start=start, end=end
        )
        if scope_ids is not None:
            # Narrow to the accounts that represent member balances so a member
            # statement never discloses executive or other-member postings.
            member_accounts = MEMBER_STATEMENT_ACCOUNT_CODES
            ledger = [
                (transaction, entry)
                for transaction, entry, _account_code in ledger
            ]

        lines: list[StatementLine] = []
        running = Decimal("0.00")
        for item in ledger:
            if len(item) == 3:
                transaction, entry, _ = item
            else:
                transaction, entry = item
            debit = Decimal(entry.debit).quantize(Decimal("0.01"))
            credit = Decimal(entry.credit).quantize(Decimal("0.01"))
            running = running + debit - credit
            lines.append(
                StatementLine(
                    posted_on=transaction.created_at.date(),
                    reference=str(transaction.id)[:8],
                    description=transaction.description or transaction.source_type,
                    debit=debit,
                    credit=credit,
                    running_balance=running,
                )
            )

        total_debit = sum((line.debit for line in lines), Decimal("0.00")).quantize(
            Decimal("0.01")
        )
        total_credit = sum((line.credit for line in lines), Decimal("0.00")).quantize(
            Decimal("0.01")
        )

        return Statement(
            chama_name=chama.name,
            chama_status=chama.status.value,
            scope_label=scope_label,
            member_name=member_label[0],
            member_number=member_label[1],
            period_from=from_day,
            period_to=to_day,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            contributions=contributions,
            lines=lines,
            total_debit=total_debit,
            total_credit=total_credit,
            closing_balance=running,
        )

    def _resolve_scope(
        self, *, actor: User, chama: Chama, membership_id: uuid.UUID | None
    ) -> tuple[Membership | None, list[uuid.UUID] | None, str, tuple[str | None, int | None]]:
        """Return (own membership, allowed membership ids or None, label, member label).

        ``None`` for the membership-id list means Chama-wide access.
        """
        membership: Membership | None = None
        try:
            membership = authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        except PermissionDeniedError:
            membership = None

        if membership is None:
            # A global platform administrator does not hold a Chama membership.
            if not is_platform_admin(self.db, user=actor):
                raise PermissionDeniedError(
                    "You are not an active member of this Chama"
                )
            if membership_id is not None:
                target = get_target_membership(
                    self.db, chama_id=chama.id, membership_id=membership_id
                )
                member = target.member
                return (
                    None,
                    [target.id],
                    f"Member statement: {member.first_name} {member.last_name}",
                    (f"{member.first_name} {member.last_name}", target.membership_number),
                )
            return None, None, "Chama-wide statement (platform administrator)", (None, None)

        is_chama_wide = any(membership.has_role(role) for role in CHAMA_WIDE_ROLES)
        own_member = membership.member
        own_label = (
            f"{own_member.first_name} {own_member.last_name}",
            membership.membership_number,
        )

        if membership_id is None:
            # No filter: chair/treasurer get the whole Chama, everyone else
            # gets their own statement rather than a 403 on an omitted filter.
            if is_chama_wide:
                return membership, None, "Chama-wide statement", (None, None)
            return membership, [membership.id], "Member statement", own_label

        if not is_chama_wide and membership_id != membership.id:
            raise PermissionDeniedError("You may only download your own statement")

        if membership_id == membership.id:
            target = membership
        else:
            target = get_target_membership(
                self.db, chama_id=chama.id, membership_id=membership_id
            )
        target_member = target.member
        return (
            target,
            [target.id],
            f"Member statement: {target_member.first_name} {target_member.last_name}",
            (
                f"{target_member.first_name} {target_member.last_name}",
                target.membership_number,
            ),
        )

    def _member_account_ids(self, chama_id: uuid.UUID) -> set[str]:
        """Account codes that represent member-level balances.

        Only the seeded member-facing accounts are disclosed to plain members:
        share capital (3000) and registration fees (4000). Income, expense and
        liability accounts stay executive-only.
        """
        del chama_id
        return {"3000", "4000"}
