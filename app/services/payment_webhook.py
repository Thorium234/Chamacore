"""Provider webhook/event inbox (ADR-018).

Every inbound callback passes through a provider-neutral pipeline:

1. size check (enforced by the router reading the raw body),
2. connection resolution (callback token query parameter, then attempt binding),
3. verification (provider ``verify_callback`` plus the per-connection token),
4. payload hash and event identity,
5. deduplication by ``(connection, provider_event_id)`` with a payload-hash
   disagreement check,
6. parsing and storage of the raw payload under the retention policy,
7. a safe state transition with amount matching and out-of-order handling.

Callbacks advance the payment attempt and intent state machines (ADR-016) and,
when the intent carries a ``contribution_id`` and reaches SUCCEEDED, settle the
linked contribution through the OQ-013 ledger posting path as the system user
(ADR-019). Disagreements surface as ``DISAGREEMENT`` events for reconciliation
rather than a silent override.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.callback_utils import constant_time_equal, connection_callback_token, payload_hash
from app.core.config import get_settings
from app.core.errors import RateLimitError, WebhookRejectedError
from app.core.ratelimit import RateLimiter
from app.models.enums import (
    PaymentEnvironment,
    PaymentEventStatus,
    PaymentProviderCode,
    PaymentTransferSource,
    ProviderTransactionStatus,
)
from app.models.payment_event import PaymentEvent
from app.providers import provider_registry
from app.repositories.payment import (
    PaymentAttemptRepository,
    PaymentConnectionRepository,
    PaymentEventRepository,
    PaymentIntentRepository,
    ProviderTransactionRepository,
)
from app.services.settlement import settle_linked_contribution

_webhook_limiter = RateLimiter(get_settings().payment_webhook_per_minute_limit, 60.0)


def check_webhook_rate_limit(key: str) -> None:
    if not _webhook_limiter.allow(key):
        raise RateLimitError("Too many webhook deliveries; try again shortly")


class PaymentWebhookService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.connections = PaymentConnectionRepository(db)
        self.attempts = PaymentAttemptRepository(db)
        self.provider_transactions = ProviderTransactionRepository(db)
        self.events = PaymentEventRepository(db)
        self.intents = PaymentIntentRepository(db)

    def handle(
        self,
        *,
        provider_code: PaymentProviderCode,
        environment: PaymentEnvironment,
        raw_payload: bytes,
        headers: dict[str, str],
        query_params: dict[str, str],
    ) -> PaymentEvent:
        """Process one raw provider callback and return the stored event."""
        if len(raw_payload) > self.settings.payment_webhook_max_body_bytes:
            raise WebhookRejectedError("Callback body exceeds the size limit")

        adapter = provider_registry.get(provider_code, environment)
        parsed = adapter.parse_callback(raw_payload=raw_payload)
        connection = self._resolve_connection(provider_code, environment, parsed, query_params)

        ok, _reason = adapter.verify_callback(raw_payload=raw_payload, headers=headers)
        if not ok:
            raise WebhookRejectedError("Callback verification failed")

        event = self._store_event(connection, parsed, raw_payload)
        if event.status in (PaymentEventStatus.DEDUPLICATED, PaymentEventStatus.DISAGREEMENT):
            return event
        if event.status == PaymentEventStatus.UNPROCESSABLE:
            return event

        attempt = self._find_attempt(parsed)
        if attempt is None or attempt.connection_id != connection.id:
            event.status = PaymentEventStatus.UNPROCESSABLE
            event.processed_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(event)
            return event

        return self._apply_callback(attempt, parsed, event)

    # -- connection resolution ----------------------------------------------

    def _resolve_connection(
        self,
        provider_code: PaymentProviderCode,
        environment: PaymentEnvironment,
        parsed,
        query_params: dict[str, str],
    ):
        """Bind the callback to a connection: callback token, then attempt ids."""
        token = query_params.get("token")
        connection_id_raw = query_params.get("connection_id")

        if token:
            if not connection_id_raw:
                raise WebhookRejectedError("Callback token supplied without a connection id")
            try:
                connection_id = uuid.UUID(connection_id_raw)
            except ValueError as exc:
                raise WebhookRejectedError("Callback connection id is invalid") from exc
            connection = self.connections.get_by_id(connection_id)
            if connection is None:
                raise WebhookRejectedError("Callback connection does not exist")
            expected = connection_callback_token(
                connection_id=connection.id,
                provider_code=connection.provider_code,
                environment=connection.environment,
            )
            if not constant_time_equal(token, expected):
                raise WebhookRejectedError("Callback token is invalid")
            self._check_connection_match(connection, provider_code, environment)
            return connection

        attempt = self._find_attempt(parsed)
        if attempt is None:
            raise WebhookRejectedError("Callback does not reference a known payment attempt")
        connection = attempt.connection
        self._check_connection_match(connection, provider_code, environment)
        return connection

    @staticmethod
    def _check_connection_match(connection, provider_code, environment) -> None:
        if connection.provider_code != provider_code or connection.environment != environment:
            raise WebhookRejectedError(
                "Callback provider and environment do not match the connection"
            )

    def _find_attempt(self, parsed):
        if parsed.provider_request_id:
            attempt = self.attempts.get_by_provider_request_id(parsed.provider_request_id)
            if attempt is not None:
                return attempt
        if parsed.provider_transaction_id:
            transaction = self.provider_transactions.get_by_provider_transaction_id(
                parsed.provider_transaction_id
            )
            if transaction is not None:
                return transaction.payment_attempt
        return None

    # -- storage and deduplication ------------------------------------------

    def _store_event(
        self, connection, parsed, raw_payload: bytes
    ) -> PaymentEvent:
        digest = payload_hash(raw_payload)
        existing = None
        if parsed.provider_event_id:
            existing = self.events.get_by_connection_event(
                connection.id, parsed.provider_event_id
            )
            if existing is not None:
                if existing.payload_hash != digest:
                    existing.status = PaymentEventStatus.DISAGREEMENT
                    existing.processed_at = datetime.now(timezone.utc)
                    self.db.commit()
                    self.db.refresh(existing)
                    return existing
                existing.status = PaymentEventStatus.DEDUPLICATED
                existing.processed_at = datetime.now(timezone.utc)
                self.db.commit()
                self.db.refresh(existing)
                return existing

        event = PaymentEvent(
            id=uuid.uuid4(),
            connection_id=connection.id,
            provider_code=connection.provider_code,
            environment=connection.environment,
            provider_event_id=parsed.provider_event_id,
            payload_hash=digest,
            raw_payload=raw_payload.decode("utf-8", errors="replace"),
            status=PaymentEventStatus.RECEIVED,
            received_at=datetime.now(timezone.utc),
            last_transition_source="PROVIDER_CALLBACK",
        )
        self.db.add(event)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing = None
            if parsed.provider_event_id:
                existing = self.events.get_by_connection_event(
                    connection.id, parsed.provider_event_id
                )
            if existing is not None:
                if existing.payload_hash != digest:
                    existing.status = PaymentEventStatus.DISAGREEMENT
                    existing.processed_at = datetime.now(timezone.utc)
                else:
                    existing.status = PaymentEventStatus.DEDUPLICATED
                    existing.processed_at = datetime.now(timezone.utc)
                self.db.commit()
                self.db.refresh(existing)
                return existing
            raise
        self.db.refresh(event)
        if not parsed.is_parseable:
            event.status = PaymentEventStatus.UNPROCESSABLE
            event.processed_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(event)
        return event

    # -- state application --------------------------------------------------

    def _apply_callback(self, attempt, parsed, event: PaymentEvent) -> PaymentEvent:
        from app.models.enums import PaymentAttemptStatus, PaymentIntentStatus
        from app.models.provider_transaction import ProviderTransaction
        from app.services.payment_intent import max_attempt_numbers

        normalized = parsed.normalized_status
        intent = attempt.payment_intent
        now = datetime.now(timezone.utc)

        if parsed.amount is not None and parsed.amount != intent.amount:
            event.status = PaymentEventStatus.DISAGREEMENT
            event.processed_at = now
            self.db.commit()
            self.db.refresh(event)
            return event
        if parsed.currency is not None and parsed.currency != intent.currency:
            event.status = PaymentEventStatus.DISAGREEMENT
            event.processed_at = now
            self.db.commit()
            self.db.refresh(event)
            return event

        current = attempt.status
        if normalized in (
            None,
            ProviderTransactionStatus.PENDING,
            ProviderTransactionStatus.UNKNOWN,
        ):
            event.status = PaymentEventStatus.UNPROCESSABLE
            event.processed_at = now
            self.db.commit()
            self.db.refresh(event)
            return event

        if current == PaymentAttemptStatus.SUCCEEDED:
            event.status = (
                PaymentEventStatus.PROCESSED
                if normalized == ProviderTransactionStatus.SUCCEEDED
                else PaymentEventStatus.DISAGREEMENT
            )
            event.processed_at = now
            self.db.commit()
            self.db.refresh(event)
            return event

        if current == PaymentAttemptStatus.FAILED:
            event.status = (
                PaymentEventStatus.PROCESSED
                if normalized == ProviderTransactionStatus.FAILED
                else PaymentEventStatus.DISAGREEMENT
            )
            event.processed_at = now
            self.db.commit()
            self.db.refresh(event)
            return event

        attempt.last_transition_source = PaymentTransferSource.PROVIDER_CALLBACK
        transaction = self.provider_transactions.get_by_attempt(attempt.id)
        if transaction is None:
            transaction = ProviderTransaction(
                payment_attempt_id=attempt.id,
                connection_id=attempt.connection_id,
                normalized_status=ProviderTransactionStatus.UNKNOWN,
            )
            self.db.add(transaction)

        if normalized == ProviderTransactionStatus.SUCCEEDED:
            attempt.status = PaymentAttemptStatus.SUCCEEDED
            attempt.completed_at = now
            transaction.normalized_status = ProviderTransactionStatus.SUCCEEDED
            if parsed.provider_transaction_id:
                transaction.provider_transaction_id = parsed.provider_transaction_id
                attempt.provider_transaction_id = parsed.provider_transaction_id
            if parsed.raw_status:
                transaction.raw_status = parsed.raw_status
            if intent.status == PaymentIntentStatus.PROCESSING:
                intent.status = PaymentIntentStatus.SUCCEEDED
                intent.last_transition_source = PaymentTransferSource.PROVIDER_CALLBACK
                intent.last_transition_by_user_id = None
            if intent.contribution_id is not None:
                settle_linked_contribution(self.db, payment_intent=intent)
        else:
            attempt.status = PaymentAttemptStatus.FAILED
            attempt.completed_at = now
            attempt.failure_code = parsed.error_code
            attempt.failure_message_safe = parsed.error_message_safe
            transaction.normalized_status = ProviderTransactionStatus.FAILED
            if parsed.raw_status:
                transaction.raw_status = parsed.raw_status
            if attempt.attempt_number >= max_attempt_numbers():
                if intent.status == PaymentIntentStatus.PROCESSING:
                    intent.status = PaymentIntentStatus.FAILED
                    intent.last_transition_source = PaymentTransferSource.PROVIDER_CALLBACK
                    intent.last_transition_by_user_id = None

        event.status = PaymentEventStatus.PROCESSED
        event.processed_at = now
        self.db.commit()
        self.db.refresh(event)
        return event