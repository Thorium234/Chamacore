"""Safaricom Daraja adapter: STK Push (Lipa Na M-Pesa Online) (ADR-016).

Sandbox and production are separate adapter instances with distinct base
URLs, so a sandbox connection can never call a production endpoint.

Documented provider behaviour (recorded per mission requirement):

- OAuth token: ``GET /oauth/v1/generate?grant_type=client_credentials`` with
  HTTP Basic (consumer key / consumer secret). Tokens last ~1 hour.
- STK Push: ``POST /mpesa/stkpush/v1/processrequest`` with a Bearer token
  and ``Password = base64(ShortCode + Passkey + Timestamp)`` where the
  timestamp is EAT ``YYYYMMDDHHmmss``.
- A ``ResponseCode`` of ``0`` means the prompt was queued — NOT that money
  moved. Confirmation is the async callback (or the STK query endpoint).
- Status query: ``POST /mpesa/stkpushquery/v1/query`` keyed on
  ``CheckoutRequestID``.
- Callback payload: ``Body.stkCallback`` with ``CheckoutRequestID``,
  ``ResultCode`` (0 = success), and ``CallbackMetadata.Item``.
- Callback verification limitation: Daraja provides no per-payload signature
  or hash. Security therefore relies on HTTPS callback URLs, a secret
  per-connection callback token, strict attempt binding (the callback must
  reference a CheckoutRequestID we created), amount matching, and event
  deduplication (ADR-018).
"""

import base64
import re
import threading
import time
from datetime import datetime, timedelta, timezone
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

SANDBOX_BASE_URL = "https://sandbox.safaricom.co.ke"
PRODUCTION_BASE_URL = "https://api.safaricom.co.ke"
DEFAULT_COUNTRY = "KE"

FAILURE_RESULT_CODES = {
    "1": "insufficient balance",
    "1032": "request cancelled by customer",
    "1034": "transaction rejected",
    "1037": "USSD timeout (no PIN)",
    "2001": "invalid transaction / PIN attempts exhausted",
}

DARAJA_CAPABILITIES = frozenset(
    {"STK_PUSH", "PAYMENT_STATUS_QUERY", "CALLBACKS"}
)

# Daraja OAuth tokens last ~1 hour. Cache per consumer key for well under
# that (50 minutes) so repeated STK Push/status-query calls in a window do
# not re-request a token on every call.
TOKEN_CACHE_TTL_SECONDS = 50 * 60


def normalize_phone(raw: str) -> str:
    """Normalize a Kenyan phone to 2547XXXXXXXX (12 digits) form."""
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("0"):
        digits = "254" + digits[1:]
    elif digits.startswith("7") or digits.startswith("1"):
        digits = "254" + digits
    if not re.fullmatch(r"2547\d{8}", digits):
        raise ProviderIntegrationError(
            "PHONE_FORMAT",
            "Daraja STK Push requires a Safaricom number in 2547XXXXXXXX format",
        )
    return digits


class DarajaAdapter(ProviderPort):
    provider_code = PaymentProviderCode.DARAJA
    name = "Daraja"

    def __init__(
        self,
        environment: PaymentEnvironment,
        *,
        http_client: httpx.Client | None = None,
        timeout: float | None = None,
    ):
        if environment not in (PaymentEnvironment.SANDBOX, PaymentEnvironment.PRODUCTION):
            raise ValueError(f"Unsupported environment {environment}")
        self.environment = environment
        base_url = SANDBOX_BASE_URL if environment == PaymentEnvironment.SANDBOX else PRODUCTION_BASE_URL
        if http_client is not None:
            self._http = ProviderHttpClient(base_url, timeout)
            self._http._client = http_client
        else:
            self._http = ProviderHttpClient(base_url, timeout)
        # Token cache is per adapter instance. The provider registry holds one
        # Sandbox and one Production adapter for the process, so production
        # traffic shares the cache while tests (fresh instances) stay isolated.
        self._token_cache: dict[str, tuple[str, float]] = {}
        self._token_lock = threading.Lock()

    @property
    def spec(self) -> ProviderSpec:
        return ProviderSpec(
            code=PaymentProviderCode.DARAJA,
            name="Daraja",
            capabilities=DARAJA_CAPABILITIES,
            supported_environments=frozenset(
                {PaymentEnvironment.SANDBOX, PaymentEnvironment.PRODUCTION}
            ),
        )

    # -- credential handling -------------------------------------------------

    def decrypted_credentials(self, credentials: dict, context: ConnectionContext) -> dict:
        required = {"consumer_key", "consumer_secret", "short_code", "passkey"}
        missing = required - set(credentials)
        if missing:
            raise ProviderIntegrationError(
                "CREDENTIALS_INCOMPLETE",
                "Daraja credentials are missing required fields",
            )
        unknown = set(credentials) - required
        if unknown:
            raise ProviderIntegrationError(
                "CREDENTIALS_UNEXPECTED",
                "Daraja credentials contain unsupported fields",
            )
        return {key: credentials[key] for key in required}

    def masked_account_identifier(self, credentials: dict) -> str:
        short_code = credentials.get("short_code", "")
        return f"****{short_code[-4:]}"

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
            token = self._access_token(shaped["consumer_key"], shaped["consumer_secret"])
        except ProviderIntegrationError:
            return CredentialValidationResult(
                valid=False,
                error_code="AUTH_FAILED",
                error_message_safe="Daraja rejected the consumer key or consumer secret",
            )
        if token is None:
            return CredentialValidationResult(
                valid=False,
                error_code="AUTH_FAILED",
                error_message_safe="Daraja rejected the consumer key or consumer secret",
            )
        return CredentialValidationResult(
            valid=True,
            masked_account_identifier=self.masked_account_identifier(shaped),
        )

    def _access_token(self, consumer_key: str, consumer_secret: str) -> str | None:
        now = time.monotonic()
        with self._token_lock:
            cached = self._token_cache.get(consumer_key)
            if cached is not None and cached[1] > now:
                return cached[0]
        credentials = base64.b64encode(
            f"{consumer_key}:{consumer_secret}".encode()
        ).decode("ascii")
        response = self._http.request(
            "GET",
            "/oauth/v1/generate",
            params={"grant_type": "client_credentials"},
            headers={
                "Authorization": f"Basic {credentials}",
                "Cache-Control": "no-cache",
            },
        )
        if response.status_code != 200:
            with self._token_lock:
                self._token_cache.pop(consumer_key, None)
            raise ProviderIntegrationError(
                "AUTH_FAILED", "Daraja OAuth token request failed"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            with self._token_lock:
                self._token_cache.pop(consumer_key, None)
            raise ProviderIntegrationError(
                "AUTH_MALFORMED", "Daraja OAuth response was not JSON"
            ) from exc
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            with self._token_lock:
                self._token_cache.pop(consumer_key, None)
            raise ProviderIntegrationError(
                "AUTH_MALFORMED", "Daraja OAuth response did not include an access token"
            )
        with self._token_lock:
            self._token_cache[consumer_key] = (
                token,
                time.monotonic() + TOKEN_CACHE_TTL_SECONDS,
            )
        return token

    # -- payment attempt -----------------------------------------------------

    @staticmethod
    def _daraja_timestamp(when: datetime) -> str:
        eat = when.astimezone(timezone(timedelta(hours=3)))
        return eat.strftime("%Y%m%d%H%M%S")

    def create_payment_attempt(
        self, *, credentials: dict, request: PaymentAttemptRequest, context: ConnectionContext
    ) -> PaymentAttemptResult:
        shaped = self.decrypted_credentials(credentials, context)
        amount = self._require_integer_kes(request.amount)
        phone = normalize_phone(request.customer_phone)
        short_code = str(shaped["short_code"])
        token = self._access_token(shaped["consumer_key"], shaped["consumer_secret"])
        timestamp = self._daraja_timestamp(datetime.now(timezone.utc))
        password = base64.b64encode(
            f"{short_code}{shaped['passkey']}{timestamp}".encode()
        ).decode("ascii")

        body = {
            "BusinessShortCode": short_code,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone,
            "PartyB": short_code,
            "PhoneNumber": phone,
            "CallBackURL": request.callback_url,
            "AccountReference": request.charge_reference[:12],
            "TransactionDesc": request.client_reference[:13] or "ChamaCore payment",
        }
        response = self._http.request(
            "POST",
            "/mpesa/stkpush/v1/processrequest",
            headers={"Authorization": f"Bearer {token}"},
            json=body,
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderIntegrationError(
                "RESPONSE_MALFORMED", "Daraja STK Push response was not JSON"
            ) from exc

        response_code = str(payload.get("ResponseCode"))
        checkout_request_id = payload.get("CheckoutRequestID")
        merchant_request_id = payload.get("MerchantRequestID")

        if response_code == "0" and isinstance(checkout_request_id, str) and checkout_request_id:
            return PaymentAttemptResult(
                accepted=True,
                provider_request_id=checkout_request_id,
                provider_transaction_id=merchant_request_id or None,
                normalized_status=ProviderTransactionStatus.PENDING,
            )

        message = payload.get(
            "ResponseDescription",
            payload.get("CustomerMessage", "Daraja did not accept the STK Push request"),
        )
        return PaymentAttemptResult(
            accepted=False,
            normalized_status=ProviderTransactionStatus.FAILED,
            retryable=False,
            error_code=f"DARAJA_{response_code or 'UNKNOWN'}",
            error_message_safe=self._safe_message(str(message)),
        )

    @staticmethod
    def _require_integer_kes(amount: Decimal) -> str:
        try:
            quantized = amount.quantize(Decimal("1"))
        except InvalidOperation as exc:
            raise ProviderIntegrationError(
                "AMOUNT_INVALID", "Daraja STK Push amount is invalid"
            ) from exc
        if quantized != amount:
            raise ProviderIntegrationError(
                "AMOUNT_NOT_INTEGER",
                "Daraja STK Push requires a whole-number KES amount",
            )
        return str(quantized)

    def query_payment_status(
        self,
        *,
        credentials: dict,
        provider_request_id: str | None,
        client_reference: str,
        context: ConnectionContext,
    ) -> StatusQueryResult:
        shaped = self.decrypted_credentials(credentials, context)
        if not provider_request_id:
            raise ProviderIntegrationError(
                "QUERY_REFERENCE_MISSING",
                "No provider request id is available to query Daraja",
            )
        token = self._access_token(shaped["consumer_key"], shaped["consumer_secret"])
        timestamp = self._daraja_timestamp(datetime.now(timezone.utc))
        short_code = str(shaped["short_code"])
        password = base64.b64encode(
            f"{short_code}{shaped['passkey']}{timestamp}".encode()
        ).decode("ascii")
        body = {
            "BusinessShortCode": short_code,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": provider_request_id,
        }
        response = self._http.request(
            "POST",
            "/mpesa/stkpushquery/v1/query",
            headers={"Authorization": f"Bearer {token}"},
            json=body,
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderIntegrationError(
                "RESPONSE_MALFORMED", "Daraja status query response was not JSON"
            ) from exc

        result_code = str(payload.get("ResultCode"))
        if result_code == "1037":
            return StatusQueryResult(
                found=True,
                provider_request_id=provider_request_id,
                normalized_status=ProviderTransactionStatus.UNKNOWN,
                raw_status="ResultCode 1037 (timeout)",
            )
        if result_code == "0":
            return StatusQueryResult(
                found=True,
                provider_request_id=provider_request_id,
                provider_transaction_id=self._metadata_value(payload, "MpesaReceiptNumber"),
                normalized_status=ProviderTransactionStatus.SUCCEEDED,
                raw_status="ResultCode 0",
            )
        return StatusQueryResult(
            found=True,
            provider_request_id=provider_request_id,
            normalized_status=ProviderTransactionStatus.FAILED,
            raw_status=f"ResultCode {result_code}",
            error_code=f"DARAJA_{result_code}",
            error_message_safe=(
                FAILURE_RESULT_CODES.get(result_code, "Daraja reported a failed transaction")
            ),
        )

    @staticmethod
    def _metadata_value(payload: dict, wanted_name: str) -> str | None:
        try:
            items = payload["CallbackMetadata"]["Item"]
        except (KeyError, TypeError):
            return None
        for item in items or []:
            if isinstance(item, dict) and item.get("Name") == wanted_name:
                value = item.get("Value")
                return None if value is None else str(value)
        return None

    # -- callbacks -----------------------------------------------------------

    def parse_callback(self, *, raw_payload: bytes) -> ParsedCallback:
        try:
            payload = raw_payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            return ParsedCallback(provider_event_id=None)
        try:
            import json

            body = json.loads(payload)
            stk = body["Body"]["stkCallback"]
        except (ValueError, KeyError, TypeError):
            return ParsedCallback(provider_event_id=None)

        checkout_request_id = stk.get("CheckoutRequestID")
        result_code = stk.get("ResultCode")
        if not isinstance(checkout_request_id, str) or not checkout_request_id:
            return ParsedCallback(provider_event_id=None)

        amount = self._metadata_value(stk, "Amount")
        receipt = self._metadata_value(stk, "MpesaReceiptNumber")
        phone = self._metadata_value(stk, "PhoneNumber")

        normalized = (
            ProviderTransactionStatus.SUCCEEDED
            if str(result_code) == "0"
            else ProviderTransactionStatus.FAILED
        )
        try:
            parsed_amount = Decimal(amount) if amount is not None else None
        except (InvalidOperation, TypeError):
            parsed_amount = None

        return ParsedCallback(
            provider_event_id=checkout_request_id,
            provider_request_id=checkout_request_id,
            provider_transaction_id=receipt,
            amount=parsed_amount,
            currency="KES",
            payer_phone=phone,
            normalized_status=normalized,
            raw_status=f"ResultCode {result_code}",
            error_code=None if normalized == ProviderTransactionStatus.SUCCEEDED
            else f"DARAJA_{result_code}",
            error_message_safe=(
                None
                if normalized == ProviderTransactionStatus.SUCCEEDED
                else str(stk.get("ResultDesc", "Daraja reported a failed transaction"))[:480]
            ),
        )

    def verify_callback(
        self, *, raw_payload: bytes, headers: dict[str, str]
    ) -> tuple[bool, str | None]:
        # Documented limitation: Daraja exposes no per-payload signature. The
        # webhook service enforces attempt binding, the secret callback token,
        # HTTPS, size limits, and replay controls instead (ADR-018).
        return True, None

    def normalize_provider_status(self, raw: str) -> ProviderTransactionStatus:
        code = str(raw).strip()
        if code == "0":
            return ProviderTransactionStatus.SUCCEEDED
        if code in FAILURE_RESULT_CODES:
            return ProviderTransactionStatus.FAILED
        if code in ("", "1037"):
            return ProviderTransactionStatus.UNKNOWN
        return ProviderTransactionStatus.UNKNOWN

    @staticmethod
    def _safe_message(value: str) -> str:
        return " ".join(value.split())[:400]


def create_daraja_adapters() -> list[DarajaAdapter]:
    return [
        DarajaAdapter(PaymentEnvironment.SANDBOX),
        DarajaAdapter(PaymentEnvironment.PRODUCTION),
    ]