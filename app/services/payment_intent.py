"""Payment intent and attempt orchestration (ADR-016).

A payment is collected in two layers:

- ``payment_intents`` — the business-level request to collect money from a
  member, created idempotently by ``client key`` per Chama.
- ``payment_attempts`` — each provider request for an intent, including
  retries. One intent may have up to ``payment_attempt_max_retries + 1``
  attempts.

Only ``initiate`` produces provider calls and it is the single retry
orchestrator:

- no attempt yet -> create attempt #1 (intent becomes PROCESSING)
- last attempt SUCCEEDED -> idempotent return
- last attempt in-flight or ambiguous (INITIATED/TIMEOUT/UNKNOWN) -> resolve
  with a provider status query; never create a duplicate request while the
  outcome is unknown
- last attempt FAILED -> create the next attempt only when the failure was
  retryable and attempts remain; otherwise the intent becomes FAILED
  (terminal).

State machines (documented in ADR-016):

:PaymentAttempt: INITIATED -> SUCCEEDED | FAILED | TIMEOUT | UNKNOWN;
                 TIMEOUT/UNKNOWN may later resolve to SUCCEEDED/FAILED via a
                 callback or a status query. SUCCEEDED and FAILED are final
                 for that attempt row.
:PaymentIntent: PENDING -> PROCESSING (first attempt) -> SUCCEEDED | FAILED.
                SUCCEEDED and FAILED are final; a completed payment never
                regresses to PENDING.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.callback_utils import canonical_payload_hash, connection_callback_token
from app.core.config import get_settings
from app.core.credential_cipher import CredentialCipher, CredentialCipherError
from app.core.errors import ConflictError, RateLimitError, StateError
from app.core.ratelimit import RateLimiter
from app.models.enums import (
    PaymentAttemptStatus,
    PaymentIntentStatus,
    PaymentTransferSource,
    ProviderTransactionStatus,
)
from app.models.payment_attempt import PaymentAttempt
from app.models.payment_intent import PaymentIntent
from app.models.provider_transaction import ProviderTransaction
from app.models.user import User
from app.providers import provider_registry
from app.providers.base import ConnectionContext, PaymentAttemptRequest
from app.providers.errors import ProviderIntegrationError, ProviderTimeoutError
from app.repositories.payment import (
    PaymentAttemptRepository,
    PaymentConnectionRepository,
    PaymentIntentRepository,
    ProviderTransactionRepository,
)
from app.services.access import (
    authorize_chama_access,
    get_chama_or_404,
    get_target_membership,
)

# Provider failure codes that are permanent for a given credential/request and
# therefore not retried. Everything else (e.g. PROVIDER_UNREACHABLE) is
# treated as retryable; timeouts become the ambiguous TIMEOUT status.
PERMANENT_FAILURE_CODES = frozenset(
    {
        "AUTH_FAILED",
        "AUTH_MALFORMED",
        "CREDENTIALS_INCOMPLETE",
        "CREDENTIALS_UNEXPECTED",
        "SIGNING_KEY_INVALID",
        "PHONE_FORMAT",
        "AMOUNT_INVALID",
        "AMOUNT_NOT_INTEGER",
        "QUERY_REFERENCE_MISSING",
    }
)

_initiate_limiter = RateLimiter(
    get_settings().payment_initiate_daily_limit, 86_400.0
)


def max_attempt_numbers() -> int:
    """Total attempts allowed for one intent: the first plus retries."""
    return get_settings().payment_attempt_max_retries + 1


class PaymentIntentService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.cipher = CredentialCipher()
        self.intents = PaymentIntentRepository(db)
        self.attempts = PaymentAttemptRepository(db)
        self.connections = PaymentConnectionRepository(db)
        self.provider_transactions = ProviderTransactionRepository(db)

    # -- authorization ------------------------------------------------------

    def _chama(self, actor: User, chama_id: uuid.UUID):
        chama = get_chama_or_404(self.db, chama_id)
        authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        return chama

    # -- intent creation ----------------------------------------------------

    def create(
        self,
        *,
        actor: User,
        chama_id: uuid.UUID,
        membership_id: uuid.UUID,
        amount,
        currency: str,
        purpose: str,
        idempotency_key: str,
    ) -> PaymentIntent:
        """Create a payment intent idempotently by ``(chama, idempotency_key)``."""
        chama = self._chama(actor, chama_id)
        target = get_target_membership(self.db, chama_id=chama.id, membership_id=membership_id)
        if target.status.value != "ACTIVE":
            raise StateError("Payments can only be collected from active members")

        currency = currency.upper()
        payload_hash = canonical_payload_hash(
            membership_id=target.id,
            amount=f"{amount}",
            currency=currency,
            purpose=purpose,
        )

        existing = self._find_intent_by_key(chama.id, idempotency_key)
        if existing is not None:
            return self._match_idempotent_create(
                existing, target.id, amount, currency, purpose, payload_hash
            )

        intent = PaymentIntent(
            id=uuid.uuid4(),
            chama_id=chama.id,
            membership_id=target.id,
            amount=amount,
            currency=currency,
            purpose=purpose,
            status=PaymentIntentStatus.PENDING,
            idempotency_key=idempotency_key,
            idempotency_payload_hash=payload_hash,
            created_by_user_id=actor.id,
            last_transition_source=PaymentTransferSource.CLIENT,
            last_transition_by_user_id=actor.id,
        )
        self.db.add(intent)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing = self._find_intent_by_key(chama.id, idempotency_key)
            if existing is not None:
                return self._match_idempotent_create(
                    existing, target.id, amount, currency, purpose, payload_hash
                )
            raise
        self.db.refresh(intent)
        return intent

    def _find_intent_by_key(self, chama_id: uuid.UUID, idempotency_key: str):
        return self.intents.get_by_idempotency_key(chama_id, idempotency_key)

    def _match_idempotent_create(
        self,
        existing: PaymentIntent,
        membership_id: uuid.UUID,
        amount,
        currency: str,
        purpose: str,
        payload_hash: str,
    ) -> PaymentIntent:
        if existing.idempotency_payload_hash != payload_hash:
            raise ConflictError(
                "This idempotency key was already used with a different payment request"
            )
        if existing.membership_id != membership_id:
            raise ConflictError(
                "This idempotency key was already used for a different membership"
            )
        if existing.amount != amount or existing.currency != currency or existing.purpose != purpose:
            raise ConflictError(
                "This idempotency key was already used with a different amount, currency, or purpose"
            )
        return existing

    # -- read paths ---------------------------------------------------------

    def get_intent(
        self, *, actor: User, chama_id: uuid.UUID, intent_id: uuid.UUID
    ) -> PaymentIntent:
        chama = self._chama(actor, chama_id)
        intent = self.intents.get_in_chama(chama.id, intent_id)
        if intent is None:
            raise StateError("Payment intent not found in this Chama")
        return intent

    def list_intents(self, *, actor: User, chama_id: uuid.UUID) -> list[PaymentIntent]:
        chama = self._chama(actor, chama_id)
        return self.intents.list_by_chama(chama.id)

    def get_attempt(
        self, *, actor: User, chama_id: uuid.UUID, attempt_id: uuid.UUID
    ) -> PaymentAttempt:
        chama = self._chama(actor, chama_id)
        attempt = self.attempts.get_in_chama(chama.id, attempt_id)
        if attempt is None:
            raise StateError("Payment attempt not found in this Chama")
        return attempt

    def list_attempts(
        self, *, actor: User, chama_id: uuid.UUID, intent_id: uuid.UUID
    ) -> list[PaymentAttempt]:
        chama = self._chama(actor, chama_id)
        intent = self.intents.get_in_chama(chama.id, intent_id)
        if intent is None:
            raise StateError("Payment intent not found in this Chama")
        return self.attempts.list_for_intent(intent.id)

    # -- initiation and retries ----------------------------------------------

    def initiate(
        self,
        *,
        actor: User,
        chama_id: uuid.UUID,
        intent_id: uuid.UUID,
        connection_id: uuid.UUID,
    ) -> PaymentAttempt:
        """Start (or continue) provider attempts for an intent.

        Retriggering ``initiate`` is safe: it resolves in-flight attempts via
        a provider status query and never duplicates a request whose outcome
        is unknown.
        """
        chama = self._chama(actor, chama_id)
        intent = self.intents.get_in_chama(chama.id, intent_id)
        if intent is None:
            raise StateError("Payment intent not found in this Chama")

        if intent.status == PaymentIntentStatus.FAILED:
            raise StateError(
                "This payment intent has already failed; create a new payment intent"
            )
        if intent.status == PaymentIntentStatus.SUCCEEDED:
            attempt = self._last_attempt(intent)
            if attempt is not None:
                return attempt
            raise StateError("This payment intent has already been completed")

        connection = self._active_connection(chama.id, connection_id)
        self._check_initiate_rate_limit(connection.id)
        target = get_target_membership(self.db, chama_id=chama.id, membership_id=intent.membership_id)
        if target.status.value != "ACTIVE":
            raise StateError(
                "The payment target is no longer an active member of this Chama"
            )

        shaped = self._shaped_credentials(connection, chama.id)
        context = self._context(connection, chama.id)
        attempts = self.attempts.list_for_intent(intent.id)

        if not attempts:
            self._transition_intent(
                intent, PaymentIntentStatus.PROCESSING,
                PaymentTransferSource.CLIENT, actor.id,
            )
            self.db.commit()
            return self._create_attempt(intent, connection, shaped, context, 1, actor)

        last = attempts[-1]
        if last.status == PaymentAttemptStatus.SUCCEEDED:
            return last

        if last.status in (
            PaymentAttemptStatus.INITIATED,
            PaymentAttemptStatus.TIMEOUT,
            PaymentAttemptStatus.UNKNOWN,
        ):
            if self._query_and_resolve(last, connection, shaped, context):
                if last.status == PaymentAttemptStatus.SUCCEEDED:
                    return last
                last.retryable = last.failure_code not in PERMANENT_FAILURE_CODES
                self.db.commit()
            else:
                # Outcome still unknown: never create a duplicate charge.
                return last

        # ``last`` is now FAILED.
        if last.attempt_number >= max_attempt_numbers():
            self._transition_intent(
                intent, PaymentIntentStatus.FAILED,
                PaymentTransferSource.CLIENT, actor.id,
            )
            self.db.commit()
            raise StateError(
                "Payment could not be completed after the maximum number of attempts; "
                "create a new payment intent"
            )
        if not last.retryable:
            self._transition_intent(
                intent, PaymentIntentStatus.FAILED,
                PaymentTransferSource.CLIENT, actor.id,
            )
            self.db.commit()
            raise StateError(
                "The payment provider rejected this request permanently; "
                "create a new payment intent"
            )

        return self._create_attempt(
            intent, connection, shaped, context, last.attempt_number + 1, actor
        )

    def _last_attempt(self, intent: PaymentIntent) -> PaymentAttempt | None:
        attempts = self.attempts.list_for_intent(intent.id)
        return attempts[-1] if attempts else None

    def _active_connection(self, chama_id: uuid.UUID, connection_id: uuid.UUID):
        connection = self.connections.get_in_chama(chama_id, connection_id)
        if connection is None:
            raise StateError("Payment connection not found in this Chama")
        if connection.status.value != "ACTIVE":
            raise StateError("Payment connection is not active and cannot initiate payments")
        adapter = provider_registry.get(connection.provider_code, connection.environment)
        spec = adapter.spec
        if not (spec.supports("PAYMENT_REQUEST") or spec.supports("STK_PUSH")):
            raise StateError("This payment connection does not support payment initiation")
        return connection

    def _check_initiate_rate_limit(self, connection_id: uuid.UUID) -> None:
        if not _initiate_limiter.allow(str(connection_id)):
            raise RateLimitError(
                "The daily payment initiation limit for this connection was reached"
            )

    # -- attempt creation ---------------------------------------------------

    def _create_attempt(
        self,
        intent: PaymentIntent,
        connection,
        shaped: dict,
        context: ConnectionContext,
        attempt_number: int,
        actor: User,
    ) -> PaymentAttempt:
        client_reference = self._unique_client_reference(connection.id, intent.id, attempt_number)
        phone = intent.membership.member.phone_number
        callback_url = self._callback_url(connection)

        attempt = PaymentAttempt(
            id=uuid.uuid4(),
            payment_intent_id=intent.id,
            connection_id=connection.id,
            attempt_number=attempt_number,
            client_reference=client_reference,
            status=PaymentAttemptStatus.INITIATED,
            retryable=False,
            last_transition_source=PaymentTransferSource.CLIENT,
        )
        transaction = ProviderTransaction(
            payment_attempt_id=attempt.id,
            connection_id=connection.id,
            normalized_status=ProviderTransactionStatus.UNKNOWN,
        )
        adapter = provider_registry.get(connection.provider_code, connection.environment)
        request = PaymentAttemptRequest(
            amount=intent.amount,
            currency=intent.currency,
            customer_phone=phone,
            client_reference=client_reference,
            charge_reference=self._charge_reference(intent),
            callback_url=callback_url,
        )
        now = datetime.now(timezone.utc)

        try:
            result = adapter.create_payment_attempt(
                credentials=shaped, request=request, context=context
            )
        except ProviderTimeoutError as exc:
            attempt.status = PaymentAttemptStatus.TIMEOUT
            attempt.retryable = True
            attempt.failure_code = exc.code
            attempt.failure_message_safe = exc.message_safe
            transaction.normalized_status = ProviderTransactionStatus.UNKNOWN
            transaction.raw_status = exc.code
            self.db.add_all([attempt, transaction])
            self.db.commit()
            self.db.refresh(attempt)
            return attempt
        except ProviderIntegrationError as exc:
            attempt.status = PaymentAttemptStatus.FAILED
            attempt.retryable = exc.code not in PERMANENT_FAILURE_CODES
            attempt.failure_code = exc.code
            attempt.failure_message_safe = exc.message_safe
            attempt.completed_at = now
            transaction.normalized_status = ProviderTransactionStatus.FAILED
            transaction.raw_status = exc.code
            self.db.add_all([attempt, transaction])
            self.db.commit()
            self.db.refresh(attempt)
            return attempt

        if result.accepted:
            attempt.status = PaymentAttemptStatus.INITIATED
            attempt.provider_request_id = result.provider_request_id
            attempt.provider_transaction_id = result.provider_transaction_id
            transaction.provider_request_id = result.provider_request_id
            transaction.provider_transaction_id = result.provider_transaction_id
            transaction.normalized_status = result.normalized_status
            if intent.status == PaymentIntentStatus.PENDING:
                self._transition_intent(
                    intent, PaymentIntentStatus.PROCESSING,
                    PaymentTransferSource.CLIENT, actor.id,
                )
            self.db.add(attempt)
            self.db.add(transaction)
            self.db.commit()
            self.db.refresh(attempt)
            return attempt

        attempt.status = PaymentAttemptStatus.FAILED
        attempt.retryable = result.retryable
        attempt.failure_code = result.error_code
        attempt.failure_message_safe = result.error_message_safe
        attempt.completed_at = now
        transaction.normalized_status = result.normalized_status
        transaction.raw_status = result.error_code
        self.db.add_all([attempt, transaction])
        self.db.commit()
        self.db.refresh(attempt)
        return attempt

    def _unique_client_reference(
        self, connection_id: uuid.UUID, intent_id: uuid.UUID, attempt_number: int
    ) -> str:
        base = f"PAY-{intent_id.hex[:16]}-{attempt_number:02d}"
        candidate = base
        counter = 0
        while self.db.scalars(
            select(PaymentAttempt.id).where(
                PaymentAttempt.connection_id == connection_id,
                PaymentAttempt.client_reference == candidate,
            )
        ).first() is not None:
            counter += 1
            candidate = f"{base}-{counter}"
        return candidate

    @staticmethod
    def _charge_reference(intent: PaymentIntent) -> str:
        return f"CHAMACORE-{intent.id.hex[:16].upper()}"

    def _callback_url(self, connection) -> str:
        base = self.settings.public_base_url.rstrip("/")
        token = connection_callback_token(
            connection_id=connection.id,
            provider_code=connection.provider_code,
            environment=connection.environment,
        )
        prefix = self.settings.api_v1_prefix
        return (
            f"{base}{prefix}/payments/webhooks/{connection.provider_code.value}/"
            f"{connection.environment.value}?connection_id={connection.id}&token={token}"
        )

    # -- status resolution --------------------------------------------------

    def _query_and_resolve(
        self, attempt: PaymentAttempt, connection, shaped: dict, context: ConnectionContext
    ) -> bool:
        """Query the provider for an ambiguous attempt; True when resolved."""
        if not attempt.provider_request_id:
            return False
        adapter = provider_registry.get(connection.provider_code, connection.environment)
        now = datetime.now(timezone.utc)
        try:
            result = adapter.query_payment_status(
                credentials=shaped,
                provider_request_id=attempt.provider_request_id,
                client_reference=attempt.client_reference,
                context=context,
            )
        except (ProviderIntegrationError, ProviderTimeoutError):
            return False

        transaction = self.provider_transactions.get_by_attempt(attempt.id)
        if transaction is None:
            transaction = ProviderTransaction(
                payment_attempt_id=attempt.id, connection_id=connection.id
            )
            self.db.add(transaction)
        transaction.last_queried_at = now
        if result.provider_request_id:
            transaction.provider_request_id = result.provider_request_id
        if result.provider_transaction_id:
            transaction.provider_transaction_id = result.provider_transaction_id
        if result.raw_status:
            transaction.raw_status = result.raw_status
        transaction.normalized_status = result.normalized_status

        if result.normalized_status == ProviderTransactionStatus.SUCCEEDED:
            self._resolve_attempt_success(attempt)
            return True
        if result.normalized_status == ProviderTransactionStatus.FAILED:
            self._resolve_attempt_failure(
                attempt, result.error_code, result.error_message_safe
            )
            return True
        return False

    def _resolve_attempt_success(self, attempt: PaymentAttempt) -> None:
        now = datetime.now(timezone.utc)
        attempt.status = PaymentAttemptStatus.SUCCEEDED
        attempt.completed_at = now
        attempt.last_transition_source = PaymentTransferSource.STATUS_QUERY
        if attempt.payment_intent.status == PaymentIntentStatus.PROCESSING:
            self._transition_intent(
                attempt.payment_intent,
                PaymentIntentStatus.SUCCEEDED,
                PaymentTransferSource.STATUS_QUERY,
                None,
            )
        self.db.commit()

    def _resolve_attempt_failure(
        self, attempt: PaymentAttempt, failure_code: str | None, message_safe: str | None
    ) -> None:
        attempt.status = PaymentAttemptStatus.FAILED
        attempt.completed_at = datetime.now(timezone.utc)
        attempt.failure_code = failure_code
        attempt.failure_message_safe = message_safe
        attempt.last_transition_source = PaymentTransferSource.STATUS_QUERY
        self.db.commit()

    # -- shared helpers -----------------------------------------------------

    def _shaped_credentials(self, connection, chama_id: uuid.UUID) -> dict:
        try:
            payload = self.cipher.open(
                connection.encrypted_credentials,
                chama_id=chama_id,
                provider_code=connection.provider_code,
                environment=connection.environment,
                credential_version=connection.credential_version,
                connection_id=connection.id,
            )
        except CredentialCipherError as exc:
            raise StateError("Stored payment credentials could not be decrypted") from exc
        adapter = provider_registry.get(connection.provider_code, connection.environment)
        return adapter.decrypted_credentials(payload, self._context(connection, chama_id))

    def _context(self, connection, chama_id: uuid.UUID) -> ConnectionContext:
        return ConnectionContext(
            connection_id=connection.id,
            chama_id=chama_id,
            provider_code=connection.provider_code,
            environment=connection.environment,
            status=connection.status,
            credential_version=connection.credential_version,
        )

    def _transition_intent(
        self,
        intent: PaymentIntent,
        new_status: PaymentIntentStatus,
        source: PaymentTransferSource,
        user_id: uuid.UUID | None,
    ) -> None:
        allowed = {
            PaymentIntentStatus.PENDING: {PaymentIntentStatus.PROCESSING},
            PaymentIntentStatus.PROCESSING: {
                PaymentIntentStatus.SUCCEEDED,
                PaymentIntentStatus.FAILED,
            },
            PaymentIntentStatus.SUCCEEDED: set(),
            PaymentIntentStatus.FAILED: set(),
        }
        if new_status not in allowed[intent.status]:
            raise StateError(
                f"Payment intent cannot move from {intent.status.value} to {new_status.value}"
            )
        intent.status = new_status
        intent.last_transition_source = source
        intent.last_transition_by_user_id = user_id