"""Payment-connection credential lifecycle service (ADR-017).

Chairperson-only lifecycle: create, replace, validate/test, disable/revoke,
and delete (delete only when the connection has no payment history). Secrets
are encrypted with AES-GCM before persistence and never leave through
schemas, logs, exceptions, or repr output.

Connection status policy (ADR-017):

- create -> PENDING_VALIDATION
- validation success -> ACTIVE (except a DISABLED connection stays DISABLED:
  'validate' on DISABLED is a test-only action that never re-enables)
- validation failure -> INVALID (except DISABLED stays DISABLED)
- replace credentials -> PENDING_VALIDATION (must re-validate)
- disable -> DISABLED (blocks all new attempts; history preserved)
- delete -> allowed only for connections with no payment attempts/events
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.credential_cipher import CredentialCipher, CredentialCipherError
from app.core.callback_utils import connection_callback_token
from app.core.config import get_settings
from app.core.errors import ConflictError, RateLimitError, StateError
from app.core.ratelimit import RateLimiter
from app.models.enums import (
    PaymentConnectionAuditAction,
    PaymentConnectionStatus,
    PaymentEnvironment,
    PaymentProviderCode,
)
from app.models.payment_attempt import PaymentAttempt
from app.models.payment_connection import PaymentConnection
from app.models.payment_connection_audit import PaymentConnectionAudit
from app.models.payment_event import PaymentEvent
from app.models.user import User
from app.providers import provider_registry
from app.providers.base import C2BRegisterRequest, ConnectionContext
from app.providers.errors import ProviderIntegrationError, UnknownProviderError
from app.providers.schemas import ProviderCredentials
from app.repositories.payment import PaymentConnectionRepository
from app.schemas.payment import C2BRegisterUrlOut
from app.services.access import (
    RoleName,
    authorize_chama_access,
    get_chama_or_404,
    require_role,
)

_validate_limiter = RateLimiter(get_settings().payment_validate_per_minute_limit, 60.0)
_c2b_register_limiter = RateLimiter(get_settings().payment_validate_per_minute_limit, 60.0)


class PaymentConnectionService:
    def __init__(self, db: Session):
        self.db = db
        self.connections = PaymentConnectionRepository(db)
        self.cipher = CredentialCipher()

    def _chairperson_chama(self, actor: User, chama_id: uuid.UUID):
        chama = get_chama_or_404(self.db, chama_id)
        membership = authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        require_role(membership, RoleName.CHAIRPERSON)
        return chama

    def _member_chama(self, actor: User, chama_id: uuid.UUID):
        chama = get_chama_or_404(self.db, chama_id)
        authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        return chama

    def _adapter(self, provider_code: PaymentProviderCode, environment: PaymentEnvironment):
        try:
            return provider_registry.get(provider_code, environment)
        except UnknownProviderError as exc:
            raise StateError("This payment provider is not supported") from exc

    @staticmethod
    def _credential_payload(credentials: ProviderCredentials) -> dict:
        payload = {}
        for key, value in credentials.model_dump().items():
            if value is None:
                continue
            payload[key] = value.get_secret_value() if hasattr(value, "get_secret_value") else value
        return payload

    def create(
        self,
        *,
        actor: User,
        chama_id: uuid.UUID,
        provider_code: PaymentProviderCode,
        environment: PaymentEnvironment,
        credentials: ProviderCredentials,
    ) -> PaymentConnection:
        chama = self._chairperson_chama(actor, chama_id)
        adapter = self._adapter(provider_code, environment)

        existing = self.connections.get_by_provider_environment(chama.id, provider_code, environment)
        if existing is not None:
            raise ConflictError(
                "This Chama already has a connection for this provider and environment"
            )

        connection = PaymentConnection(
            id=uuid.uuid4(),
            chama_id=chama.id,
            provider_code=provider_code,
            environment=environment,
            status=PaymentConnectionStatus.PENDING_VALIDATION,
            encryption_key_version=1,
            credential_version=1,
            created_by_user_id=actor.id,
            updated_by_user_id=actor.id,
        )
        payload = self._credential_payload(credentials)
        connection.encrypted_credentials = self.cipher.seal(
            payload,
            chama_id=chama.id,
            provider_code=provider_code,
            environment=environment,
            credential_version=connection.credential_version,
            connection_id=connection.id,
        )
        connection.masked_account_identifier = adapter.masked_account_identifier(payload)

        self.db.add(connection)
        self._audit(
            connection=connection,
            actor=actor,
            action=PaymentConnectionAuditAction.CREATED,
            previous_status=None,
            new_status=PaymentConnectionStatus.PENDING_VALIDATION,
        )
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ConflictError(
                "This Chama already has a connection for this provider and environment"
            )
        self.db.refresh(connection)
        return connection

    def list(self, *, actor: User, chama_id: uuid.UUID) -> list[PaymentConnection]:
        chama = self._member_chama(actor, chama_id)
        return self.connections.list_by_chama(chama.id)

    def get(
        self, *, actor: User, chama_id: uuid.UUID, connection_id: uuid.UUID
    ) -> PaymentConnection:
        self._member_chama(actor, chama_id)
        connection = self.connections.get_in_chama(chama_id, connection_id)
        if connection is None:
            raise StateError("Payment connection not found in this Chama")
        return connection

    def replace(
        self,
        *,
        actor: User,
        chama_id: uuid.UUID,
        connection_id: uuid.UUID,
        credentials: ProviderCredentials,
    ) -> PaymentConnection:
        chama = self._chairperson_chama(actor, chama_id)
        connection = self.connections.get_in_chama(chama.id, connection_id)
        if connection is None:
            raise StateError("Payment connection not found in this Chama")

        adapter = self._adapter(connection.provider_code, connection.environment)
        payload = self._credential_payload(credentials)
        next_version = connection.credential_version + 1
        connection.encrypted_credentials = self.cipher.seal(
            payload,
            chama_id=chama.id,
            provider_code=connection.provider_code,
            environment=connection.environment,
            credential_version=next_version,
            connection_id=connection.id,
        )
        connection.credential_version = next_version
        connection.masked_account_identifier = adapter.masked_account_identifier(payload)
        connection.last_validation_error_code = None
        connection.updated_by_user_id = actor.id

        previous_status = connection.status
        connection.status = PaymentConnectionStatus.PENDING_VALIDATION
        self._audit(
            connection=connection,
            actor=actor,
            action=PaymentConnectionAuditAction.CREDENTIALS_REPLACED,
            previous_status=previous_status,
            new_status=PaymentConnectionStatus.PENDING_VALIDATION,
        )
        self.db.commit()
        self.db.refresh(connection)
        return connection

    def validate(
        self, *, actor: User, chama_id: uuid.UUID, connection_id: uuid.UUID
    ) -> PaymentConnection:
        chama = self._chairperson_chama(actor, chama_id)
        connection = self.connections.get_in_chama(chama.id, connection_id)
        if connection is None:
            raise StateError("Payment connection not found in this Chama")
        if connection.status == PaymentConnectionStatus.ACTIVE:
            raise StateError("Payment connection is already active")
        if not _validate_limiter.allow(str(connection.id)):
            raise RateLimitError(
                "Too many validation attempts for this connection; try again shortly"
            )

        adapter = self._adapter(connection.provider_code, connection.environment)
        context = self._context(connection, chama.id)
        was_disabled = connection.status == PaymentConnectionStatus.DISABLED
        now = datetime.now(timezone.utc)

        try:
            payload = self.cipher.open(
                connection.encrypted_credentials,
                chama_id=chama.id,
                provider_code=connection.provider_code,
                environment=connection.environment,
                credential_version=connection.credential_version,
                connection_id=connection.id,
            )
            result = adapter.validate_credentials(credentials=payload, context=context)
        except (CredentialCipherError, UnknownProviderError) as exc:
            if not was_disabled:
                connection.status = PaymentConnectionStatus.INVALID
            connection.last_validated_at = now
            connection.last_validation_error_code = (
                "DECRYPT_FAILED" if isinstance(exc, CredentialCipherError) else "PROVIDER_UNSUPPORTED"
            )
            connection.updated_by_user_id = actor.id
            self._audit(
                connection=connection,
                actor=actor,
                action=(
                    PaymentConnectionAuditAction.TESTED
                    if was_disabled
                    else PaymentConnectionAuditAction.VALIDATED
                ),
                previous_status=None,
                new_status=connection.status,
            )
            self.db.commit()
            self.db.refresh(connection)
            return connection

        if result.valid:
            if was_disabled:
                connection.status = PaymentConnectionStatus.DISABLED
                audit_action = PaymentConnectionAuditAction.TESTED
            else:
                connection.status = PaymentConnectionStatus.ACTIVE
                audit_action = PaymentConnectionAuditAction.VALIDATED
            if result.masked_account_identifier:
                connection.masked_account_identifier = result.masked_account_identifier
            connection.last_validated_at = now
            connection.last_validation_error_code = None
        else:
            if not was_disabled:
                connection.status = PaymentConnectionStatus.INVALID
            connection.last_validated_at = now
            connection.last_validation_error_code = result.error_code or "VALIDATION_FAILED"
            audit_action = (
                PaymentConnectionAuditAction.TESTED
                if was_disabled
                else PaymentConnectionAuditAction.VALIDATED
            )

        connection.updated_by_user_id = actor.id
        self._audit(
            connection=connection,
            actor=actor,
            action=audit_action,
            previous_status=None,
            new_status=connection.status,
        )
        self.db.commit()
        self.db.refresh(connection)
        return connection

    def register_c2b_urls(
        self,
        *,
        actor: User,
        chama_id: uuid.UUID,
        connection_id: uuid.UUID,
        response_type: str = "Completed",
    ) -> C2BRegisterUrlOut:
        """Activate Daraja C2B (manual Paybill) callbacks for a connection."""
        chama = self._chairperson_chama(actor, chama_id)
        connection = self.connections.get_in_chama(chama.id, connection_id)
        if connection is None:
            raise StateError("Payment connection not found in this Chama")
        if connection.provider_code != PaymentProviderCode.DARAJA:
            raise StateError("C2B Register-URL activation is only supported for Daraja")
        if not _c2b_register_limiter.allow(str(connection.id)):
            raise RateLimitError(
                "Too many register-url attempts for this connection; try again shortly"
            )

        settings = get_settings()
        base_url = settings.public_base_url.rstrip("/")
        prefix = settings.api_v1_prefix.strip("/")
        token = connection_callback_token(
            connection_id=connection.id,
            provider_code=connection.provider_code,
            environment=connection.environment,
        )
        validation_url = (
            f"{base_url}/{prefix}/payments/c2b/validate/{connection.id}?token={token}"
        )
        confirmation_url = (
            f"{base_url}/{prefix}/payments/c2b/confirm/{connection.id}?token={token}"
        )

        adapter = self._adapter(connection.provider_code, connection.environment)
        context = self._context(connection, chama.id)
        try:
            payload = self.cipher.open(
                connection.encrypted_credentials,
                chama_id=chama.id,
                provider_code=connection.provider_code,
                environment=connection.environment,
                credential_version=connection.credential_version,
                connection_id=connection.id,
            )
            result = adapter.register_c2b_urls(
                credentials=payload,
                request=C2BRegisterRequest(
                    short_code=payload["short_code"],
                    validation_url=validation_url,
                    confirmation_url=confirmation_url,
                    response_type=response_type,
                ),
                context=context,
            )
        except CredentialCipherError as exc:
            raise StateError("Connection credentials could not be decrypted") from exc
        except KeyError as exc:
            raise StateError("Connection credentials are missing the short code") from exc
        except ProviderIntegrationError as exc:
            raise StateError(
                f"C2B Register-URL was rejected by the provider ({exc.code}); "
                "the shortcode still answers the old URLs"
            ) from exc

        return C2BRegisterUrlOut(
            accepted=result.accepted,
            response_code=result.response_code or "",
            response_description=result.response_description or "",
            validation_url=validation_url,
            confirmation_url=confirmation_url,
        )

    def disable(
        self, *, actor: User, chama_id: uuid.UUID, connection_id: uuid.UUID
    ) -> PaymentConnection:
        chama = self._chairperson_chama(actor, chama_id)
        connection = self.connections.get_in_chama(chama.id, connection_id)
        if connection is None:
            raise StateError("Payment connection not found in this Chama")

        if connection.status == PaymentConnectionStatus.DISABLED:
            self.db.refresh(connection)
            return connection

        previous_status = connection.status
        connection.status = PaymentConnectionStatus.DISABLED
        connection.updated_by_user_id = actor.id
        self._audit(
            connection=connection,
            actor=actor,
            action=PaymentConnectionAuditAction.DISABLED,
            previous_status=previous_status,
            new_status=PaymentConnectionStatus.DISABLED,
        )
        self.db.commit()
        self.db.refresh(connection)
        return connection

    def delete(
        self, *, actor: User, chama_id: uuid.UUID, connection_id: uuid.UUID
    ) -> None:
        chama = self._chairperson_chama(actor, chama_id)
        connection = self.connections.get_in_chama(chama.id, connection_id)
        if connection is None:
            raise StateError("Payment connection not found in this Chama")
        if self._has_payment_history(connection.id):
            raise ConflictError(
                "This connection has payment history and cannot be deleted; disable it instead"
            )
        self._audit(
            connection=connection,
            actor=actor,
            action=PaymentConnectionAuditAction.DELETED,
            previous_status=connection.status,
            new_status=None,
        )
        self.db.delete(connection)
        self.db.commit()

    def _has_payment_history(self, connection_id: uuid.UUID) -> bool:
        attempts = self.db.scalar(
            select(func.count()).select_from(PaymentAttempt).where(
                PaymentAttempt.connection_id == connection_id
            )
        )
        events = self.db.scalar(
            select(func.count()).select_from(PaymentEvent).where(
                PaymentEvent.connection_id == connection_id
            )
        )
        return bool(attempts or events)

    def _context(self, connection: PaymentConnection, chama_id: uuid.UUID) -> ConnectionContext:
        return ConnectionContext(
            connection_id=connection.id,
            chama_id=chama_id,
            provider_code=connection.provider_code,
            environment=connection.environment,
            status=connection.status,
            credential_version=connection.credential_version,
        )

    def _audit(
        self,
        *,
        connection: PaymentConnection,
        actor: User,
        action: PaymentConnectionAuditAction,
        previous_status,
        new_status,
    ) -> None:
        self.db.add(
            PaymentConnectionAudit(
                connection_id=connection.id,
                actor_user_id=actor.id,
                action=action,
                previous_status=previous_status,
                new_status=new_status,
                credential_version=connection.credential_version,
            )
        )