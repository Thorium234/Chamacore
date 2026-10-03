"""Repositories for the V3 payment domain (ADR-016)."""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import (
    PaymentEnvironment,
    PaymentEventStatus,
    PaymentIntentStatus,
    PaymentProviderCode,
)
from app.models.payment_attempt import PaymentAttempt
from app.models.payment_connection import PaymentConnection
from app.models.payment_event import PaymentEvent
from app.models.payment_intent import PaymentIntent
from app.models.provider_transaction import ProviderTransaction
from app.repositories.base import BaseRepository


class PaymentConnectionRepository(BaseRepository):
    def get_by_id(self, connection_id: uuid.UUID) -> PaymentConnection | None:
        return self.db.get(PaymentConnection, connection_id)

    def get_in_chama(
        self, chama_id: uuid.UUID, connection_id: uuid.UUID
    ) -> PaymentConnection | None:
        return self.db.scalars(
            select(PaymentConnection).where(
                PaymentConnection.id == connection_id,
                PaymentConnection.chama_id == chama_id,
            )
        ).first()

    def get_by_provider_environment(
        self,
        chama_id: uuid.UUID,
        provider_code: PaymentProviderCode,
        environment: PaymentEnvironment,
    ) -> PaymentConnection | None:
        return self.db.scalars(
            select(PaymentConnection).where(
                PaymentConnection.chama_id == chama_id,
                PaymentConnection.provider_code == provider_code,
                PaymentConnection.environment == environment,
            )
        ).first()

    def list_by_chama(
        self, chama_id: uuid.UUID, *, limit: int | None = None, offset: int = 0
    ) -> list[PaymentConnection]:
        stmt = (
            select(PaymentConnection)
            .where(PaymentConnection.chama_id == chama_id)
            .order_by(PaymentConnection.provider_code, PaymentConnection.environment)
        )
        if limit is not None:
            stmt = stmt.limit(limit).offset(offset)
        return list(self.db.scalars(stmt))


class PaymentIntentRepository(BaseRepository):
    def get_in_chama(self, chama_id: uuid.UUID, intent_id: uuid.UUID) -> PaymentIntent | None:
        return self.db.scalars(
            select(PaymentIntent).where(
                PaymentIntent.id == intent_id,
                PaymentIntent.chama_id == chama_id,
            )
        ).first()

    def get_by_idempotency_key(
        self, chama_id: uuid.UUID, idempotency_key: str
    ) -> PaymentIntent | None:
        return self.db.scalars(
            select(PaymentIntent).where(
                PaymentIntent.chama_id == chama_id,
                PaymentIntent.idempotency_key == idempotency_key,
            )
        ).first()

    def list_by_chama(
        self,
        chama_id: uuid.UUID,
        *,
        limit: int | None = None,
        offset: int = 0,
        membership_id: uuid.UUID | None = None,
    ) -> list[PaymentIntent]:
        stmt = select(PaymentIntent).where(PaymentIntent.chama_id == chama_id)
        if membership_id is not None:
            stmt = stmt.where(PaymentIntent.membership_id == membership_id)
        stmt = stmt.order_by(PaymentIntent.created_at.desc(), PaymentIntent.id.desc())
        if limit is not None:
            stmt = stmt.limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def count_by_status(self, status: PaymentIntentStatus) -> int:
        """Global count of intents in one status (bounded observability signal)."""
        stmt = (
            select(func.count())
            .select_from(PaymentIntent)
            .where(PaymentIntent.status == status)
        )
        return int(self.db.scalar(stmt) or 0)


class PaymentAttemptRepository(BaseRepository):
    def get(self, attempt_id: uuid.UUID) -> PaymentAttempt | None:
        return self.db.scalars(
            select(PaymentAttempt).options(selectinload(PaymentAttempt.payment_intent),
                                          selectinload(PaymentAttempt.connection)).where(
                PaymentAttempt.id == attempt_id
            )
        ).first()

    def get_in_chama(self, chama_id: uuid.UUID, attempt_id: uuid.UUID) -> PaymentAttempt | None:
        return self.db.scalars(
            select(PaymentAttempt)
            .join(PaymentIntent, PaymentIntent.id == PaymentAttempt.payment_intent_id)
            .options(selectinload(PaymentAttempt.payment_intent),
                     selectinload(PaymentAttempt.connection))
            .where(
                PaymentAttempt.id == attempt_id,
                PaymentIntent.chama_id == chama_id,
            )
        ).first()

    def get_by_provider_request_id(self, provider_request_id: str) -> PaymentAttempt | None:
        return self.db.scalars(
            select(PaymentAttempt)
            .options(selectinload(PaymentAttempt.payment_intent),
                     selectinload(PaymentAttempt.connection))
            .where(PaymentAttempt.provider_request_id == provider_request_id)
        ).first()

    def list_for_intent(self, intent_id: uuid.UUID) -> list[PaymentAttempt]:
        stmt = (
            select(PaymentAttempt)
            .options(selectinload(PaymentAttempt.connection))
            .where(PaymentAttempt.payment_intent_id == intent_id)
            .order_by(PaymentAttempt.attempt_number)
        )
        return list(self.db.scalars(stmt))

    def last_attempt_number(self, intent_id: uuid.UUID) -> int:
        attempts = self.list_for_intent(intent_id)
        return attempts[-1].attempt_number if attempts else 0


class ProviderTransactionRepository(BaseRepository):
    def get_by_attempt(self, attempt_id: uuid.UUID) -> ProviderTransaction | None:
        return self.db.scalars(
            select(ProviderTransaction).where(
                ProviderTransaction.payment_attempt_id == attempt_id
            )
        ).first()

    def get_by_provider_request_id(self, provider_request_id: str) -> ProviderTransaction | None:
        return self.db.scalars(
            select(ProviderTransaction).where(
                ProviderTransaction.provider_request_id == provider_request_id
            )
        ).first()

    def get_by_provider_transaction_id(self, provider_transaction_id: str) -> ProviderTransaction | None:
        return self.db.scalars(
            select(ProviderTransaction).where(
                ProviderTransaction.provider_transaction_id == provider_transaction_id
            )
        ).first()


class PaymentEventRepository(BaseRepository):
    def get_by_connection_event(
        self, connection_id: uuid.UUID, provider_event_id: str
    ) -> PaymentEvent | None:
        return self.db.scalars(
            select(PaymentEvent).where(
                PaymentEvent.connection_id == connection_id,
                PaymentEvent.provider_event_id == provider_event_id,
            )
        ).first()

    def list_stale(
        self, *, older_than: datetime, limit: int = 100
    ) -> list[PaymentEvent]:
        """List callbacks stuck in ``RECEIVED`` past ``older_than``.

        These events were stored but their callback application never
        finished; re-delivery resumes them (see PaymentWebhookService).
        """
        stmt = (
            select(PaymentEvent)
            .where(
                PaymentEvent.status == PaymentEventStatus.RECEIVED,
                PaymentEvent.received_at < older_than,
            )
            .order_by(PaymentEvent.received_at, PaymentEvent.id)
            .limit(limit)
        )
        return list(self.db.scalars(stmt))

    def count_stale(self, *, older_than: datetime) -> int:
        """Total ``RECEIVED`` events older than ``older_than`` (untruncated)."""
        stmt = (
            select(func.count())
            .select_from(PaymentEvent)
            .where(
                PaymentEvent.status == PaymentEventStatus.RECEIVED,
                PaymentEvent.received_at < older_than,
            )
        )
        return int(self.db.scalar(stmt) or 0)
