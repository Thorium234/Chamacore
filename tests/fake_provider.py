"""A controllable ProviderPort double for service-level payment tests."""

import json
from decimal import Decimal, InvalidOperation

from app.models.enums import (
    PaymentEnvironment,
    PaymentProviderCode,
    ProviderTransactionStatus,
)
from app.providers.base import (
    C2BParsedPayload,
    C2BRegisterResult,
    ConnectionContext,
    CredentialValidationResult,
    ParsedCallback,
    PaymentAttemptResult,
    ProviderPort,
    ProviderSpec,
    StatusQueryResult,
)
from app.providers.errors import ProviderIntegrationError

FAKE_CAPABILITIES = frozenset(
    {
        "PAYMENT_REQUEST",
        "STK_PUSH",
        "PAYMENT_STATUS_QUERY",
        "CALLBACKS",
        "C2B_VALIDATION",
        "C2B_CONFIRMATION",
        "C2B_REGISTER_URL",
    }
)


class FakeAdapter(ProviderPort):
    """ProviderPort implementation whose responses are configured per test."""

    name = "Fake"

    def __init__(
        self,
        provider_code: PaymentProviderCode,
        environment: PaymentEnvironment,
    ):
        self.provider_code = provider_code
        self.environment = environment
        self.valid_credentials = True
        self.create_results: dict[str, PaymentAttemptResult] = {}
        self.create_exceptions: dict[str, Exception] = {}
        self.query_results: dict[str, StatusQueryResult] = {}
        self.verify_result: tuple[bool, str | None] = (True, None)
        self.parse_callback_fn = None
        self.register_c2b_error: ProviderIntegrationError | None = None
        self.last_register_request = None

    def register_c2b_urls(
        self, *, credentials: dict, request, context: ConnectionContext
    ) -> C2BRegisterResult:
        if self.register_c2b_error is not None:
            raise self.register_c2b_error
        self.last_register_request = request
        return C2BRegisterResult(
            accepted=True,
            response_code="0",
            response_description="Success",
        )

    def parse_c2b_validation(self, *, raw_payload: bytes) -> C2BParsedPayload:
        return self._parse_c2b(raw_payload)

    def parse_c2b_confirmation(self, *, raw_payload: bytes) -> C2BParsedPayload:
        return self._parse_c2b(raw_payload)

    @staticmethod
    def _parse_c2b(raw_payload: bytes) -> C2BParsedPayload:
        try:
            parsed = json.loads(raw_payload.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return C2BParsedPayload()
        if not isinstance(parsed, dict):
            return C2BParsedPayload()
        trans_id = parsed.get("TransID")
        if not trans_id:
            return C2BParsedPayload()
        return C2BParsedPayload(
            transaction_id=str(trans_id),
            business_short_code=str(parsed.get("BusinessShortCode") or ""),
            amount=Decimal(str(parsed["TransAmount"])) if parsed.get("TransAmount") else None,
            bill_ref_number=str(parsed.get("BillRefNumber") or ""),
            msisdn=str(parsed.get("MSISDN") or ""),
            first_name=str(parsed.get("FirstName") or ""),
            middle_name=str(parsed.get("MiddleName") or ""),
            last_name=str(parsed.get("LastName") or ""),
        )

    @property
    def spec(self) -> ProviderSpec:
        return ProviderSpec(
            code=self.provider_code,
            name=self.name,
            capabilities=FAKE_CAPABILITIES,
            supported_environments=frozenset({self.environment}),
        )

    def validate_credentials(
        self, *, credentials: dict, context: ConnectionContext
    ) -> CredentialValidationResult:
        if self.valid_credentials:
            return CredentialValidationResult(
                valid=True, masked_account_identifier="****1001"
            )
        return CredentialValidationResult(
            valid=False,
            error_code="AUTH_FAILED",
            error_message_safe="fake auth failure",
        )

    def create_payment_attempt(
        self, *, credentials: dict, request, context: ConnectionContext
    ) -> PaymentAttemptResult:
        if request.client_reference in self.create_exceptions:
            raise self.create_exceptions[request.client_reference]
        if request.client_reference in self.create_results:
            return self.create_results[request.client_reference]
        return PaymentAttemptResult(
            accepted=True,
            provider_request_id=f"REQ-{request.client_reference}",
            normalized_status=ProviderTransactionStatus.PENDING,
        )

    def query_payment_status(
        self,
        *,
        credentials: dict,
        provider_request_id: str | None,
        client_reference: str,
        context: ConnectionContext,
    ) -> StatusQueryResult:
        if provider_request_id in self.query_results:
            return self.query_results[provider_request_id]
        return StatusQueryResult(
            found=True,
            provider_request_id=provider_request_id,
            normalized_status=ProviderTransactionStatus.UNKNOWN,
        )

    def parse_callback(self, *, raw_payload: bytes) -> ParsedCallback:
        if self.parse_callback_fn is not None:
            return self.parse_callback_fn(raw_payload)
        try:
            parsed = json.loads(raw_payload.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return ParsedCallback(provider_event_id=None)
        if not isinstance(parsed, dict) or not parsed.get("provider_event_id"):
            return ParsedCallback(provider_event_id=None)
        amount = parsed.get("amount")
        try:
            amount = Decimal(str(amount)) if amount is not None else None
        except InvalidOperation:
            amount = None
        status_raw = parsed.get("normalized_status")
        return ParsedCallback(
            provider_event_id=str(parsed["provider_event_id"]),
            provider_request_id=parsed.get("provider_request_id"),
            provider_transaction_id=parsed.get("provider_transaction_id"),
            amount=amount,
            currency=parsed.get("currency"),
            payer_phone=parsed.get("payer_phone"),
            normalized_status=(
                ProviderTransactionStatus(status_raw) if status_raw else None
            ),
            raw_status=status_raw,
        )

    def verify_callback(
        self, *, raw_payload: bytes, headers: dict[str, str]
    ) -> tuple[bool, str | None]:
        return self.verify_result

    def normalize_provider_status(self, raw: str) -> ProviderTransactionStatus:
        try:
            return ProviderTransactionStatus(str(raw).upper())
        except ValueError:
            return ProviderTransactionStatus.UNKNOWN

    def masked_account_identifier(self, credentials: dict) -> str:
        return "****1001"

    def redact(self, *, key: str, value: str) -> str:
        return "****" if not value else f"{value[:2]}****{value[-2:]}"

    def decrypted_credentials(self, credentials: dict, context: ConnectionContext) -> dict:
        return dict(credentials)


def setup_fake_adapter(provider_code, environment):
    """Register a fresh FakeAdapter in the shared registry and return it."""
    from app.providers import provider_registry

    fake = FakeAdapter(provider_code, environment)
    provider_registry.register(fake)
    return fake


def restore_fake_adapter(provider_code, environment):
    """Re-register the production adapter for a provider+environment."""
    from app.providers.daraja.adapter import DarajaAdapter
    from app.providers.jenga.adapter import JengaAdapter
    from app.providers import provider_registry

    adapter_cls = JengaAdapter if provider_code == PaymentProviderCode.JENGA else DarajaAdapter
    provider_registry.register(adapter_cls(environment))