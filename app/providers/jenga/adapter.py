"""Jenga (Finserve Africa) adapter: M-Pesa STK Push via api-checkout (ADR-016).

Sandbox and production are separate adapter instances with distinct base
URLs, so a sandbox connection can never call a production endpoint.

Documented provider behaviour (recorded per mission requirement):

- Authentication: ``POST {base}/authentication/api/v3/authenticate/merchant``
  with ``Api-Key`` header and ``{"merchantCode", "consumerSecret"}`` returns a
  short-lived JWT bearer token.
- STK Push (wallet settlement): ``POST {base}/api-checkout/mpesa-stk-push/
  v3.0/init`` with Bearer token and a ``Signature`` header. The endpoint
  payload is an ``order``/``customer``/``payment`` envelope.
- Status: ``GET {base}/api-checkout/mpesa-stk-push/v3.0/status/order/
  {orderReference}`` with Bearer token.
- IPN callback: Jenga posts completion/outcome to the merchant
  ``payment.callbackUrl``.

Recorded limitations:

- The exact Jenga ``Signature`` canonical string for the STK push endpoint is
  product-specific and must be confirmed with Jenga before go-live. The
  adapter signs the concatenation of the required request values in the
  documented order when a signing private key is configured, and otherwise
  omits the header (configurable, documented).
- Jenga's IPN payload contract for the api-checkout product is
  merchant-specific; the adapter implements the documented v1 shape in
  ``parse_callback`` and records verification as a limitation. Incoming
  callbacks are therefore bound to known attempts, callback tokens, amount
  matching, and deduplication by the webhook service (ADR-018).
"""

import base64
import hashlib
import re
from decimal import Decimal, InvalidOperation

import httpx

from app.core.config import get_settings
from app.models.enums import (
    PaymentEnvironment,
    PaymentProviderCode,
    ProviderTransactionStatus,
)
from app.providers.base import (
    ConnectionContext,
    CredentialValidationResult,
    ParsedCallback,
    PaymentAttemptRequest,
    PaymentAttemptResult,
    ProviderPort,
    ProviderSpec,
    StatusQueryResult,
)
from app.providers.errors import ProviderIntegrationError
from app.providers.http import ProviderHttpClient

SANDBOX_BASE_URL = "https://uat.finserve.africa"
PRODUCTION_BASE_URL = "https://api.finserve.africa"

JENGA_CAPABILITIES = frozenset(
    {"PAYMENT_REQUEST", "PAYMENT_STATUS_QUERY", "CALLBACKS"}
)


class JengaAdapter(ProviderPort):
    provider_code = PaymentProviderCode.JENGA
    name = "Jenga"

    def __init__(
        self,
        environment: PaymentEnvironment,
        *,
        http_client: httpx.Client | None = None,
        timeout: float | None = None,
        attempt_signature: bool = True,
    ):
        if environment not in (PaymentEnvironment.SANDBOX, PaymentEnvironment.PRODUCTION):
            raise ValueError(f"Unsupported environment {environment}")
        self.environment = environment
        self.attempt_signature = attempt_signature
        base_url = (
            SANDBOX_BASE_URL if environment == PaymentEnvironment.SANDBOX else PRODUCTION_BASE_URL
        )
        if http_client is not None:
            self._http = ProviderHttpClient(base_url, timeout)
            self._http._client = http_client
        else:
            self._http = ProviderHttpClient(base_url, timeout)

    @property
    def spec(self) -> ProviderSpec:
        return ProviderSpec(
            code=PaymentProviderCode.JENGA,
            name="Jenga",
            capabilities=JENGA_CAPABILITIES,
            supported_environments=frozenset(
                {PaymentEnvironment.SANDBOX, PaymentEnvironment.PRODUCTION}
            ),
        )

    # -- credential handling -------------------------------------------------

    def decrypted_credentials(self, credentials: dict, context: ConnectionContext) -> dict:
        required = {"api_key", "merchant_code", "consumer_secret"}
        missing = required - set(credentials)
        if missing:
            raise ProviderIntegrationError(
                "CREDENTIALS_INCOMPLETE",
                "Jenga credentials are missing required fields",
            )
        allowed = required | {"signing_private_key"}
        unknown = set(credentials) - allowed
        if unknown:
            raise ProviderIntegrationError(
                "CREDENTIALS_UNEXPECTED",
                "Jenga credentials contain unsupported fields",
            )
        return {key: value for key, value in credentials.items() if key in allowed}

    def masked_account_identifier(self, credentials: dict) -> str:
        merchant = credentials.get("merchant_code", "")
        return f"****{merchant[-4:]}"

    def redact(self, *, key: str, value: str) -> str:
        if not value:
            return "****"
        if len(value) <= 4:
            return "****"
        return f"{value[:2]}****{value[-2:]}"

    # -- credentials validation ----------------------------------------------

    def validate_credentials(
        self, *, credentials: dict, context: ConnectionContext
    ) -> CredentialValidationResult:
        shaped = self.decrypted_credentials(credentials, context)
        try:
            token = self._access_token(shaped)
        except ProviderIntegrationError:
            return CredentialValidationResult(
                valid=False,
                error_code="AUTH_FAILED",
                error_message_safe="Jenga rejected the API key, merchant code, or consumer secret",
            )
        if token is None:
            return CredentialValidationResult(
                valid=False,
                error_code="AUTH_FAILED",
                error_message_safe="Jenga rejected the API key, merchant code, or consumer secret",
            )
        return CredentialValidationResult(
            valid=True,
            masked_account_identifier=self.masked_account_identifier(shaped),
        )

    def _access_token(self, shaped: dict) -> str | None:
        response = self._http.request(
            "POST",
            "/authentication/api/v3/authenticate/merchant",
            headers={"Api-Key": str(shaped["api_key"])},
            json={
                "merchantCode": str(shaped["merchant_code"]),
                "consumerSecret": str(shaped["consumer_secret"]),
            },
        )
        if response.status_code != 200:
            raise ProviderIntegrationError(
                "AUTH_FAILED", "Jenga authentication request failed"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderIntegrationError(
                "AUTH_MALFORMED", "Jenga authentication response was not JSON"
            ) from exc
        if payload.get("status") is False:
            raise ProviderIntegrationError(
                "AUTH_FAILED", "Jenga rejected the merchant credentials"
            )
        token = payload.get("token")
        if isinstance(token, str) and token:
            return token
        raise ProviderIntegrationError(
            "AUTH_MALFORMED", "Jenga authentication response did not include a token"
        )

    @staticmethod
    def _signature(shaped: dict, canonical: str) -> str | None:
        private_key_pem = shaped.get("signing_private_key")
        if not private_key_pem:
            return None
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        try:
            private_key = serialization.load_pem_private_key(
                private_key_pem.encode("utf-8"), password=None
            )
        except ValueError as exc:
            raise ProviderIntegrationError(
                "SIGNING_KEY_INVALID",
                "The Jenga signing private key could not be loaded",
            ) from exc
        signature = private_key.sign(
            canonical.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode("ascii")

    # -- payment attempt -----------------------------------------------------

    def create_payment_attempt(
        self, *, credentials: dict, request: PaymentAttemptRequest, context: ConnectionContext
    ) -> PaymentAttemptResult:
        shaped = self.decrypted_credentials(credentials, context)
        token = self._access_token(shaped)
        phone = self._normalize_phone(request.customer_phone)

        body = {
            "order": {
                "orderReference": request.client_reference,
                "orderAmount": str(request.amount),
                "orderCurrency": request.currency,
                "source": "APICHECKOUT",
                "countryCode": "KE",
                "description": self._short_text(request.charge_reference + " chama payment", 120),
            },
            "customer": {
                "name": self._short_text("chama member", 120),
                "email": self._short_text("member@chamacore.invalid", 120),
                "phoneNumber": phone,
                "identityNumber": self._short_text(request.client_reference, 50),
            },
            "payment": {
                "paymentReference": self._reference(request.client_reference),
                "paymentCurrency": request.currency,
                "channel": "MOBILE",
                "service": "MPESA",
                "provider": "JENGA",
                "callbackUrl": request.callback_url,
                "details": {
                    "msisdn": phone,
                    "paymentAmount": str(request.amount),
                },
            },
        }
        headers = {"Authorization": f"Bearer {token}"}
        if self.attempt_signature:
            signature = self._signature(shaped, self._canonical_stk_request(body))
            if signature is not None:
                headers["Signature"] = signature

        response = self._http.request(
            "POST",
            "/api-checkout/mpesa-stk-push/v3.0/init",
            headers=headers,
            json=body,
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderIntegrationError(
                "RESPONSE_MALFORMED", "Jenga STK Push response was not JSON"
            ) from exc

        if payload.get("status") is False or payload.get("code", 0) != 0:
            message = payload.get("message", "Jenga did not accept the STK Push request")
            return PaymentAttemptResult(
                accepted=False,
                normalized_status=ProviderTransactionStatus.FAILED,
                retryable=False,
                error_code=f"JENGA_{payload.get('code', 'UNKNOWN')}",
                error_message_safe=self._safe_message(str(message)),
            )

        data = payload.get("data") or {}
        order_reference = (
            str(data.get("orderReference") or data.get("paymentReference") or "")
        )
        return PaymentAttemptResult(
            accepted=True,
            provider_request_id=order_reference or request.client_reference,
            provider_transaction_id=data.get("transactionId") or data.get("checkoutRequestID") or None,
            normalized_status=ProviderTransactionStatus.PENDING,
        )

    @staticmethod
    def _reference(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _short_text(value: str, limit: int) -> str:
        value = " ".join(value.split())
        return value[:limit]

    @staticmethod
    def _canonical_stk_request(body: dict) -> str:
        """Documented best-effort canonical string for the Jenga Signature.

        The Security & Signatures documentation describes the signature as the
        concatenation of the required request values in order; the exact
        canonical string for the STK push product must be confirmed with
        Jenga before go-live (recorded limitation)."""
        pieces = [
            str(body["order"]["orderReference"]),
            str(body["order"]["orderAmount"]),
            body["order"]["orderCurrency"],
            body["customer"]["phoneNumber"],
            str(body["payment"]["details"]["paymentAmount"]),
            body["payment"]["paymentCurrency"],
        ]
        return "".join(pieces)

    @staticmethod
    def _normalize_phone(raw: str) -> str:
        digits = re.sub(r"\D", "", raw)
        if digits.startswith("0"):
            digits = "254" + digits[1:]
        elif digits.startswith("7") or digits.startswith("1"):
            digits = "254" + digits
        if not re.fullmatch(r"2547\d{8}", digits):
            raise ProviderIntegrationError(
                "PHONE_FORMAT",
                "Jenga STK Push requires a phone number in 2547XXXXXXXX format",
            )
        return digits

    def query_payment_status(
        self,
        *,
        credentials: dict,
        provider_request_id: str | None,
        client_reference: str,
        context: ConnectionContext,
    ) -> StatusQueryResult:
        shaped = self.decrypted_credentials(credentials, context)
        order_reference = provider_request_id or client_reference
        token = self._access_token(shaped)
        response = self._http.request(
            "GET",
            f"/api-checkout/mpesa-stk-push/v3.0/status/order/{order_reference}",
            headers={"Authorization": f"Bearer {token}"},
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderIntegrationError(
                "RESPONSE_MALFORMED", "Jenga status query response was not JSON"
            ) from exc

        if payload.get("status") is False:
            return StatusQueryResult(
                found=False,
                provider_request_id=order_reference,
                normalized_status=ProviderTransactionStatus.UNKNOWN,
                raw_status=self._safe_message(
                    str(payload.get("message", "Jenga did not find the order"))
                ),
                error_code="JENGA_NOT_FOUND",
                error_message_safe="Jenga could not find the order; status is unknown",
            )

        data = payload.get("data") or {}
        order = data.get("order") or {}
        order_status = str(order.get("orderStatus", ""))
        payments = data.get("invoices") or []
        external_reference = None
        for invoice in payments:
            if isinstance(invoice, dict) and invoice.get("externalReference"):
                external_reference = str(invoice["externalReference"])
                break

        normalized = self.normalize_provider_status(order_status)
        return StatusQueryResult(
            found=True,
            provider_request_id=order_reference,
            provider_transaction_id=external_reference,
            normalized_status=normalized,
            raw_status=order_status or None,
        )

    # -- callbacks -----------------------------------------------------------

    def parse_callback(self, *, raw_payload: bytes) -> ParsedCallback:
        try:
            import json

            payload = json.loads(raw_payload.decode("utf-8"))
        except (UnicodeDecodeError, ValueError, TypeError):
            return ParsedCallback(provider_event_id=None)

        order_reference = payload.get("orderReference")
        payment_reference = payload.get("paymentReference")
        transaction_id = payload.get("transactionId")
        provider_event_id = (
            str(transaction_id) if transaction_id else str(payment_reference) if payment_reference else None
        )
        if not isinstance(order_reference, str) or not order_reference or not provider_event_id:
            return ParsedCallback(provider_event_id=None)

        status_raw = str(payload.get("status", "")).upper()
        try:
            amount = Decimal(str(payload["amount"]))
        except (KeyError, InvalidOperation, TypeError):
            amount = None

        return ParsedCallback(
            provider_event_id=provider_event_id,
            provider_request_id=order_reference,
            provider_transaction_id=str(transaction_id) if transaction_id else None,
            amount=amount,
            currency=str(payload.get("currency") or "KES").upper(),
            payer_phone=payload.get("phoneNumber"),
            normalized_status=self.normalize_provider_status(status_raw),
            raw_status=status_raw or None,
        )

    def verify_callback(
        self, *, raw_payload: bytes, headers: dict[str, str]
    ) -> tuple[bool, str | None]:
        # Recorded limitation: the api-checkout IPN payload carries a hash per
        # the Checkout reference, but its exact construction and the merchant
        # callback URL are not available to a stateless verifier. The webhook
        # service therefore relies on attempt binding, the secret callback
        # token, HTTPS, amount matching, and deduplication instead (ADR-018).
        return True, None

    def normalize_provider_status(self, raw: str) -> ProviderTransactionStatus:
        code = str(raw).strip().upper()
        if code in ("SUCCESS", "PAID", "SUCCEEDED", "2"):
            return ProviderTransactionStatus.SUCCEEDED
        if code in ("FAILED", "CANCELLED", "EXPIRED", "CANCELLED1", "1"):
            return ProviderTransactionStatus.FAILED
        if code == "-1":
            return ProviderTransactionStatus.UNKNOWN
        return ProviderTransactionStatus.UNKNOWN

    @staticmethod
    def _safe_message(value: str) -> str:
        return " ".join(str(value).split())[:400]


def create_jenga_adapters() -> list[JengaAdapter]:
    return [
        JengaAdapter(PaymentEnvironment.SANDBOX),
        JengaAdapter(PaymentEnvironment.PRODUCTION),
    ]