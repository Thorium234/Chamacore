"""Provider-neutral ports and value objects (ADR-016).

The core payment domain depends only on this module. Provider adapters
implement :class:`ProviderPort` and must never leak into the contribution,
ledger, or payment services.
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from app.models.enums import (
    PaymentConnectionStatus,
    PaymentEnvironment,
    PaymentProviderCode,
    ProviderTransactionStatus,
)


@dataclass(frozen=True)
class ProviderSpec:
    code: PaymentProviderCode
    name: str
    capabilities: frozenset[str]
    supported_environments: frozenset[PaymentEnvironment]

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities


@dataclass(frozen=True)
class ConnectionContext:
    """Non-secret connection facts passed to adapters and the webhook service."""

    connection_id: uuid.UUID
    chama_id: uuid.UUID
    provider_code: PaymentProviderCode
    environment: PaymentEnvironment
    status: PaymentConnectionStatus
    credential_version: int

    @property
    def accepts_new_attempts(self) -> bool:
        return self.status == PaymentConnectionStatus.ACTIVE


@dataclass(frozen=True)
class CredentialValidationResult:
    valid: bool
    error_code: str | None = None
    error_message_safe: str | None = None
    masked_account_identifier: str | None = None


@dataclass(frozen=True)
class PaymentAttemptRequest:
    amount: Decimal
    currency: str
    customer_phone: str
    client_reference: str
    charge_reference: str
    callback_url: str


@dataclass(frozen=True)
class PaymentAttemptResult:
    accepted: bool
    provider_request_id: str | None = None
    provider_transaction_id: str | None = None
    normalized_status: ProviderTransactionStatus = ProviderTransactionStatus.PENDING
    retryable: bool = False
    error_code: str | None = None
    error_message_safe: str | None = None


@dataclass(frozen=True)
class StatusQueryResult:
    found: bool
    provider_request_id: str | None = None
    provider_transaction_id: str | None = None
    normalized_status: ProviderTransactionStatus = ProviderTransactionStatus.PENDING
    raw_status: str | None = None
    error_code: str | None = None
    error_message_safe: str | None = None


@dataclass(frozen=True)
class ParsedCallback:
    provider_event_id: str | None
    provider_request_id: str | None = None
    provider_transaction_id: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    payer_phone: str | None = None
    normalized_status: ProviderTransactionStatus | None = None
    raw_status: str | None = None
    error_code: str | None = None
    error_message_safe: str | None = None

    @property
    def is_parseable(self) -> bool:
        return self.provider_event_id is not None and self.normalized_status is not None


class ProviderPort(ABC):
    """The one interface the payment service depends on.

    Adapters are constructed per ``(provider_code, environment)`` so a
    sandbox connection can never reach a production endpoint.
    """

    provider_code: PaymentProviderCode
    environment: PaymentEnvironment
    name: str

    @property
    @abstractmethod
    def spec(self) -> ProviderSpec:
        """Static provider metadata used by the registry."""

    @abstractmethod
    def validate_credentials(
        self, *, credentials: dict, context: ConnectionContext
    ) -> CredentialValidationResult:
        """Live-check credentials against the provider without leaking them."""

    @abstractmethod
    def create_payment_attempt(
        self, *, credentials: dict, request: PaymentAttemptRequest, context: ConnectionContext
    ) -> PaymentAttemptResult:
        """Ask the provider to initiate a charge against the customer's phone."""

    @abstractmethod
    def query_payment_status(
        self,
        *,
        credentials: dict,
        provider_request_id: str | None,
        client_reference: str,
        context: ConnectionContext,
    ) -> StatusQueryResult:
        """Resolve the current provider status for a previously accepted request."""

    @abstractmethod
    def parse_callback(self, *, raw_payload: bytes) -> ParsedCallback:
        """Normalise a raw inbound callback into domain values.

        Providers that cannot be parsed return ``ParsedCallback`` with
        ``is_parseable`` False.
        """

    @abstractmethod
    def verify_callback(
        self, *, raw_payload: bytes, headers: dict[str, str]
    ) -> tuple[bool, str | None]:
        """Apply the provider's official signature/authentication mechanism.

        Returns ``(ok, reason)`` where reason is a safe string for storage.
        Providers without a documented per-payload signature return ``(True,
        None)`` and rely on the webhook service's attempt binding, callback
        token, HTTPS, and replay controls (documented limitation in ADR).
        """

    @abstractmethod
    def normalize_provider_status(self, raw: str) -> ProviderTransactionStatus:
        """Map a provider status string to the normalized enum."""

    @abstractmethod
    def masked_account_identifier(self, credentials: dict) -> str:
        """Return a display-safe masked account identifier for the credentials."""

    @abstractmethod
    def redact(self, *, key: str, value: str) -> str:
        """Mask a single secret value for safe logging, never '***' only."""

    @abstractmethod
    def decrypted_credentials(
        self, credentials: dict, context: ConnectionContext
    ) -> dict:
        """Validate and shape the sealed credential map for a provider call.

        Implementations must reject unknown keys and missing required keys so
        no garbage payload ever reaches a provider.
        """