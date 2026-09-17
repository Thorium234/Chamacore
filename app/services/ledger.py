"""Ledger service: trusted posting, idempotency, reversal, and listing."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, StateError
from app.models.ledger_transaction import LedgerTransaction
from app.models.user import User
from app.repositories.ledger import LedgerAccountRepository, LedgerRepository
from app.services.access import authorize_chama_access, get_chama_or_404

REVERSAL_SOURCE_TYPE = "LEDGER_REVERSAL"
CENT = Decimal("0.01")


@dataclass(frozen=True)
class LedgerLine:
    account_id: uuid.UUID
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")


class LedgerService:
    def __init__(self, db: Session):
        self.db = db
        self.ledger = LedgerRepository(db)
        self.accounts = LedgerAccountRepository(db)

    def post_transaction(
        self,
        *,
        actor: User,
        chama_id: uuid.UUID,
        source_type: str,
        source_id: uuid.UUID,
        description: str | None,
        lines: list[LedgerLine],
        reverses_transaction_id: uuid.UUID | None = None,
    ) -> LedgerTransaction:
        """Post one balanced immutable ledger transaction.

        Reposting the same ``(source_type, source_id)`` is an idempotent
        retry: the existing transaction is returned only when the normalized
        payload (Chama, description, reversal reference, and ledger lines)
        matches. A conflicting retry raises ``ConflictError``.
        """
        chama = get_chama_or_404(self.db, chama_id)
        authorize_chama_access(self.db, actor=actor, chama_id=chama.id)

        lines = self._normalize_lines(lines)
        self._validate_lines(chama.id, lines)

        if source_type == REVERSAL_SOURCE_TYPE and reverses_transaction_id is None:
            raise StateError(
                "A ledger reversal must reference the transaction it reverses"
            )
        if reverses_transaction_id is not None and source_type != REVERSAL_SOURCE_TYPE:
            raise StateError("A reversal reference requires the approved reversal source type")

        existing = self.ledger.get_by_source(source_type, source_id)
        if existing is not None:
            return self._resolve_idempotent_retry(
                existing, chama.id, description, reverses_transaction_id, lines
            )
        if reverses_transaction_id is not None:
            self._validate_reversal_reference(chama.id, reverses_transaction_id)

        try:
            transaction = self.ledger.create_transaction(
                chama_id=chama.id,
                source_type=source_type,
                source_id=source_id,
                description=description,
                posted_by_user_id=actor.id,
                reverses_transaction_id=reverses_transaction_id,
                entries=[(line.account_id, line.debit, line.credit) for line in lines],
            )
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing = self.ledger.get_by_source(source_type, source_id)
            if existing is not None:
                return self._resolve_idempotent_retry(
                    existing, chama.id, description, reverses_transaction_id, lines
                )
            raise
        return transaction

    def reverse_transaction(
        self,
        *,
        actor: User,
        chama_id: uuid.UUID,
        transaction_id: uuid.UUID,
        description: str | None = None,
    ) -> LedgerTransaction:
        """Reverse an immutable ledger transaction with a compensating transaction."""
        chama = get_chama_or_404(self.db, chama_id)
        authorize_chama_access(self.db, actor=actor, chama_id=chama.id)

        transaction = self.ledger.get_by_id_in_chama(chama.id, transaction_id)
        if transaction is None:
            raise StateError("Ledger transaction not found in this Chama")

        if transaction.reverses_transaction_id is not None:
            raise StateError("A reversal transaction cannot be reversed")

        lines = [
            LedgerLine(account_id=entry.account_id, debit=entry.credit, credit=entry.debit)
            for entry in transaction.entries
        ]

        return self.post_transaction(
            actor=actor,
            chama_id=chama.id,
            source_type=REVERSAL_SOURCE_TYPE,
            source_id=transaction.id,
            description=description,
            lines=lines,
            reverses_transaction_id=transaction.id,
        )

    def list_by_chama(self, *, actor: User, chama_id: uuid.UUID) -> list[LedgerTransaction]:
        chama = get_chama_or_404(self.db, chama_id)
        authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        return self.ledger.list_by_chama(chama.id)

    def list_page(
        self,
        *,
        actor: User,
        chama_id: uuid.UUID,
        limit: int,
        before_created_at: datetime | None,
        before_id: uuid.UUID | None,
    ) -> list[LedgerTransaction]:
        chama = get_chama_or_404(self.db, chama_id)
        authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        return self.ledger.list_page(
            chama.id,
            limit=limit,
            before_created_at=before_created_at,
            before_id=before_id,
        )

    def _resolve_idempotent_retry(
        self,
        existing: LedgerTransaction,
        chama_id: uuid.UUID,
        description: str | None,
        reverses_transaction_id: uuid.UUID | None,
        lines: list[LedgerLine],
    ) -> LedgerTransaction:
        if existing.chama_id != chama_id:
            raise ConflictError("This source reference was already posted to another Chama")
        if existing.description != description:
            raise ConflictError("This source reference was already posted with a different description")
        if existing.reverses_transaction_id != reverses_transaction_id:
            raise ConflictError("This source reference was already posted with a different reversal reference")

        existing_lines = sorted(
            (entry.account_id, entry.debit, entry.credit) for entry in existing.entries
        )
        requested_lines = sorted((line.account_id, line.debit, line.credit) for line in lines)
        if existing_lines != requested_lines:
            raise ConflictError("This source reference was already posted with different ledger entries")

        return existing

    def _validate_reversal_reference(
        self, chama_id: uuid.UUID, reverses_transaction_id: uuid.UUID
    ) -> None:
        target = self.ledger.get_by_id_in_chama(chama_id, reverses_transaction_id)
        if target is None:
            raise StateError("Ledger transaction to reverse does not exist in this Chama")
        if target.reverses_transaction_id is not None:
            raise StateError("A reversal transaction cannot be reversed")
        if self.ledger.get_reversal_for(target.id) is not None:
            raise ConflictError("This ledger transaction has already been reversed")

    def _validate_lines(self, chama_id: uuid.UUID, lines: list[LedgerLine]) -> None:
        if not lines:
            raise StateError("A ledger transaction must have at least one entry")

        has_debit = False
        has_credit = False
        for line in lines:
            if line.debit < 0 or line.credit < 0:
                raise StateError("Ledger amounts cannot be negative")
            if (line.debit > 0) == (line.credit > 0):
                raise StateError("Each entry must carry exactly one of debit or credit")
            if line.debit > 0:
                has_debit = True
            else:
                has_credit = True
            account = self.accounts.get_in_chama(chama_id, line.account_id)
            if account is None:
                raise StateError(
                    "Ledger entry references an account that does not exist in this Chama"
                )

        if not has_debit or not has_credit:
            raise StateError("A ledger transaction must contain at least one debit and one credit")

        if sum((line.debit - line.credit) for line in lines) != 0:
            raise StateError("A ledger transaction must balance (total debits equal total credits)")

    @classmethod
    def _normalize_lines(cls, lines: list[LedgerLine]) -> list[LedgerLine]:
        """Quantize every amount first, then validate (ADR-013)."""
        normalized = []
        for line in lines:
            debit = cls._to_quantized(line.debit, "debit")
            credit = cls._to_quantized(line.credit, "credit")
            normalized.append(LedgerLine(account_id=line.account_id, debit=debit, credit=credit))
        return normalized

    @staticmethod
    def _to_quantized(value: object, label: str) -> Decimal:
        if isinstance(value, bool) or isinstance(value, float):
            raise StateError(f"Ledger {label} amount must be an exact Decimal, not a float")
        try:
            amount = value if isinstance(value, Decimal) else Decimal(value)
        except (TypeError, ValueError, InvalidOperation) as exc:
            raise StateError(f"Ledger {label} amount is invalid") from exc
        if not amount.is_finite():
            raise StateError(f"Ledger {label} amount must be finite")
        return amount.quantize(CENT, rounding=ROUND_HALF_UP)