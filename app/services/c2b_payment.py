"""C2B (manual Paybill money-in) validation and confirmation (ADR-016, OQ-021).

Safaricom calls the Validation URL before processing a manual Paybill payment
(yielding accept/reject) and the Confirmation URL after a successful payment
(fire-and-forget, must be acknowledged). Unlike the STK callback inbox, a C2B
payment is initiated by the customer rather than by a payment attempt, so it
binds to a connection by ``connection_id`` + callback token instead of by a
provider request id.

OQ-021 contract (ADR-019):

- A connection is a single short code bound to exactly one Chama; a payload
  whose ``BusinessShortCode`` does not match the connection is unmatched.
- ``BillRefNumber`` is the string form of the member's ``membership_number``.
- Validation ACCEPTS (``ResultCode`` 0) only when the connection is ACTIVE,
  the payload parses, the short code matches, the reference is a valid
  membership number, and the matching membership is ACTIVE. Everything else is
  REJECTED (``ResultCode`` 1) and recorded immutably; unknown references are
  also stored so reconciliation has an audit trail.
- Confirmation is stored idempotently (deduplicated by ``TransID``), creates a
  CONFIRMED contribution for the current ``YYYY-MM`` period when no open
  contribution exists (amount = ``TransAmount``), and posts the money through
  the OQ-013 ledger path as the system user. Disagreements (unmatched
  reference, inactive member, or an amount that differs from the period's open
  recorded contribution) surface as ``DISAGREEMENT`` events.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.callback_utils import constant_time_equal, connection_callback_token, payload_hash
from app.core.config import get_settings
from app.core.credential_cipher import CredentialCipher, CredentialCipherError
from app.core.errors import RateLimitError, WebhookRejectedError
from app.core.ratelimit import RateLimiter
from app.db.bootstrap import ensure_system_user, system_user_id
from app.models.contribution import Contribution
from app.models.enums import ContributionStatus, PaymentEventStatus
from app.models.payment_event import PaymentEvent
from app.providers import provider_registry
from app.providers.base import ConnectionContext
from app.repositories.contribution import ContributionRepository
from app.repositories.membership import MembershipRepository
from app.repositories.payment import PaymentConnectionRepository, PaymentEventRepository
from app.services.contribution import ContributionService

VALIDATION_EVENT_PREFIX = "C2B_VALIDATION:"
CONFIRMATION_EVENT_PREFIX = "C2B_CONFIRMATION:"

_c2b_limiter = RateLimiter(get_settings().payment_webhook_per_minute_limit, 60.0)


def check_c2b_rate_limit(kind: str, client_host: str) -> None:
    if not _c2b_limiter.allow(f"c2b:{kind}:{client_host}"):
        raise RateLimitError("Too many C2B deliveries; try again shortly")


@dataclass(frozen=True)
class C2BValidationDecision:
    result_code: int
    result_description: str
    accepted: bool = False


class C2BPaymentService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.connections = PaymentConnectionRepository(db)
        self.events = PaymentEventRepository(db)
        self.contribution_service = ContributionService(db)
        self.contributions = ContributionRepository(db)
        self.memberships = MembershipRepository(db)
        self.cipher = CredentialCipher(settings=get_settings())

    # -- validation (OQ-021) ------------------------------------------------

    def validate(
        self,
        *,
        connection_id: uuid.UUID,
        raw_payload: bytes,
        headers: dict[str, str],
        query_params: dict[str, str],
    ) -> C2BValidationDecision:
        if len(raw_payload) > self.settings.payment_webhook_max_body_bytes:
            return C2BValidationDecision(
                result_code=1, result_description="Rejected: callback body exceeds the size limit"
            )
        try:
            connection, parsed = self._bind(
                connection_id, raw_payload, query_params, capability="C2B_VALIDATION"
            )
        except WebhookRejectedError as exc:
            return C2BValidationDecision(
                result_code=1, result_description=f"Rejected: {exc.message}"
            )

        accepted, reason = self._evaluate(connection, parsed)
        self._store_event(
            connection=connection,
            raw_payload=raw_payload,
            parsed=parsed,
            event_prefix=VALIDATION_EVENT_PREFIX,
            status=PaymentEventStatus.PROCESSED if accepted else PaymentEventStatus.REJECTED,
            transition_source="C2B_VALIDATION",
        )
        return C2BValidationDecision(
            result_code=0 if accepted else 1,
            result_description=reason,
            accepted=accepted,
        )

    def _evaluate(self, connection, parsed) -> tuple[bool, str]:
        if connection.status.value != "ACTIVE":
            return False, "Rejected: the payment connection is not active"
        if parsed is None or not parsed.is_parseable:
            return False, "Rejected: the C2B payload could not be parsed"
        if not self._business_short_code_matches(connection, parsed):
            return False, "Rejected: the business short code does not match this connection"

        ref = (parsed.bill_ref_number or "").strip()
        if not ref:
            return False, "Rejected: BillRefNumber is missing"
        try:
            number = int(ref)
        except ValueError:
            return False, "Rejected: BillRefNumber is not a membership number"

        membership = self.memberships.get_by_number(connection.chama_id, number)
        if membership is None:
            return False, "Rejected: no member matches this BillRefNumber"
        if membership.status.value != "ACTIVE":
            return False, "Rejected: the matching member is not active"
        return True, f"Accepted: payment for membership number {number}"

    # -- confirmation (OQ-021) ----------------------------------------------

    def confirm(
        self,
        *,
        connection_id: uuid.UUID,
        raw_payload: bytes,
        headers: dict[str, str],
        query_params: dict[str, str],
    ) -> PaymentEvent:
        if len(raw_payload) > self.settings.payment_webhook_max_body_bytes:
            raise WebhookRejectedError("C2B confirmation body exceeds the size limit")
        connection, parsed = self._bind(
            connection_id, raw_payload, query_params, capability="C2B_CONFIRMATION"
        )

        if connection.status.value != "ACTIVE" or not parsed.is_parseable or not self._business_short_code_matches(connection, parsed):
            return self._store_event(
                connection=connection,
                raw_payload=raw_payload,
                parsed=parsed,
                event_prefix=CONFIRMATION_EVENT_PREFIX,
                status=PaymentEventStatus.UNPROCESSABLE,
                transition_source="C2B_CONFIRMATION",
            )

        event = self._store_event(
            connection=connection,
            raw_payload=raw_payload,
            parsed=parsed,
            event_prefix=CONFIRMATION_EVENT_PREFIX,
            status=PaymentEventStatus.RECEIVED,
            transition_source="C2B_CONFIRMATION",
        )
        if event.status in (PaymentEventStatus.DEDUPLICATED, PaymentEventStatus.DISAGREEMENT):
            return event

        try:
            final_status = self._settle_confirmation(connection, parsed)
        except IntegrityError:
            self.db.rollback()
            final_status = PaymentEventStatus.DISAGREEMENT
        event.status = final_status
        event.processed_at = datetime.now(timezone.utc)
        event.last_transition_source = "C2B_CONFIRMATION"
        self.db.commit()
        self.db.refresh(event)
        return event

    def _settle_confirmation(self, connection, parsed) -> PaymentEventStatus:
        if parsed.amount is None or parsed.amount <= 0:
            return PaymentEventStatus.DISAGREEMENT
        ref = (parsed.bill_ref_number or "").strip()
        try:
            number = int(ref)
        except ValueError:
            return PaymentEventStatus.DISAGREEMENT
        membership = self.memberships.get_by_number(connection.chama_id, number)
        if membership is None or membership.status.value != "ACTIVE":
            return PaymentEventStatus.DISAGREEMENT

        period = datetime.now(timezone.utc).strftime("%Y-%m")
        contribution = self._find_open_contribution(membership.id, period)
        if contribution is None:
            contribution = self.contributions.create(
                membership_id=membership.id,
                amount=parsed.amount,
                period=period,
                recorded_by_user_id=system_user_id(),
                note=f"C2B {parsed.transaction_id}" if parsed.transaction_id else "C2B Paybill",
            )
        elif contribution.status == ContributionStatus.CONFIRMED and contribution.amount == parsed.amount:
            return PaymentEventStatus.PROCESSED
        elif contribution.amount != parsed.amount:
            return PaymentEventStatus.DISAGREEMENT

        self.contribution_service._settle(
            contribution,
            ensure_system_user(self.db),
            allow_already_confirmed=True,
        )
        return PaymentEventStatus.PROCESSED

    # -- binding ------------------------------------------------------------

    def _bind(self, connection_id: uuid.UUID, raw_payload: bytes, query_params, *, capability: str):
        connection = self.connections.get_by_id(connection_id)
        if connection is None:
            raise WebhookRejectedError("C2B connection does not exist")
        token = query_params.get("token")
        if not token:
            raise WebhookRejectedError("C2B callback token is missing")
        expected = connection_callback_token(
            connection_id=connection.id,
            provider_code=connection.provider_code,
            environment=connection.environment,
        )
        if not constant_time_equal(token, expected):
            raise WebhookRejectedError("C2B callback token is invalid")
        adapter = provider_registry.get(connection.provider_code, connection.environment)
        if not adapter.spec.supports(capability):
            raise WebhookRejectedError("C2B is not supported by this connection")

        raw_parsed = (
            adapter.parse_c2b_validation(raw_payload=raw_payload)
            if capability == "C2B_VALIDATION"
            else adapter.parse_c2b_confirmation(raw_payload=raw_payload)
        )
        return connection, raw_parsed

    def _business_short_code_matches(self, connection, parsed) -> bool:
        if not parsed.is_parseable or parsed.business_short_code is None:
            return False
        adapter = provider_registry.get(connection.provider_code, connection.environment)
        try:
            payload = self.cipher.open(
                connection.encrypted_credentials,
                chama_id=connection.chama_id,
                provider_code=connection.provider_code,
                environment=connection.environment,
                credential_version=connection.credential_version,
                connection_id=connection.id,
            )
        except CredentialCipherError:
            return False
        context = ConnectionContext(
            connection_id=connection.id,
            chama_id=connection.chama_id,
            provider_code=connection.provider_code,
            environment=connection.environment,
            status=connection.status,
            credential_version=connection.credential_version,
        )
        shaped = adapter.decrypted_credentials(payload, context)
        return str(shaped.get("short_code")) == parsed.business_short_code

    def _find_open_contribution(self, membership_id: uuid.UUID, period: str) -> Contribution | None:
        stmt = select(Contribution).where(
            Contribution.membership_id == membership_id,
            Contribution.period == period,
            Contribution.status != ContributionStatus.REVERSED,
        )
        return self.db.scalars(stmt).first()

    # -- event storage ------------------------------------------------------

    def _store_event(
        self,
        *,
        connection,
        raw_payload: bytes,
        parsed,
        event_prefix: str,
        status: PaymentEventStatus,
        transition_source: str,
    ) -> PaymentEvent:
        digest = payload_hash(raw_payload)
        provider_event_id = None
        if parsed.is_parseable and parsed.transaction_id:
            provider_event_id = f"{event_prefix}{parsed.transaction_id}"

        existing = None
        if provider_event_id:
            existing = self.events.get_by_connection_event(connection.id, provider_event_id)
            if existing is not None:
                existing.status = (
                    PaymentEventStatus.DISAGREEMENT
                    if existing.payload_hash != digest
                    else PaymentEventStatus.DEDUPLICATED
                )
                existing.processed_at = datetime.now(timezone.utc)
                self.db.commit()
                self.db.refresh(existing)
                return existing

        event = PaymentEvent(
            id=uuid.uuid4(),
            connection_id=connection.id,
            provider_code=connection.provider_code,
            environment=connection.environment,
            provider_event_id=provider_event_id,
            payload_hash=digest,
            raw_payload=raw_payload.decode("utf-8", errors="replace"),
            status=status,
            received_at=datetime.now(timezone.utc),
            processed_at=datetime.now(timezone.utc),
            last_transition_source=transition_source,
        )
        self.db.add(event)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            if provider_event_id:
                existing = self.events.get_by_connection_event(connection.id, provider_event_id)
                if existing is not None:
                    existing.status = (
                        PaymentEventStatus.DISAGREEMENT
                        if existing.payload_hash != digest
                        else PaymentEventStatus.DEDUPLICATED
                    )
                    existing.processed_at = datetime.now(timezone.utc)
                    self.db.commit()
                    self.db.refresh(existing)
                    return existing
            raise
        self.db.refresh(event)
        return event