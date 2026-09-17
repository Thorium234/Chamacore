"""Contract tests for the Jenga and Daraja adapters (ADR-016).

These tests run the real adapter code against a mocked ``httpx.Transport`` so
the exact endpoints, headers, and request bodies the adapters produce are
locked down without hitting a live provider.
"""

import base64
import json
import re
import uuid
from decimal import Decimal

import httpx
import pytest

from app.models.enums import (
    PaymentConnectionStatus,
    PaymentEnvironment,
    PaymentProviderCode,
    ProviderTransactionStatus,
)
from app.providers.base import ConnectionContext, PaymentAttemptRequest
from app.providers.daraja.adapter import DarajaAdapter, create_daraja_adapters
from app.providers.errors import ProviderIntegrationError, ProviderTimeoutError
from app.providers.http import ProviderHttpClient
from app.providers.jenga.adapter import JengaAdapter, create_jenga_adapters

JENGA_SANDBOX = "https://uat.finserve.africa"
DARAJA_SANDBOX = "https://sandbox.safaricom.co.ke"

CONNECTION_ID = uuid.uuid4()
CHAMA_ID = uuid.uuid4()


def context(
    provider_code: PaymentProviderCode,
    environment: PaymentEnvironment = PaymentEnvironment.SANDBOX,
) -> ConnectionContext:
    return ConnectionContext(
        connection_id=CONNECTION_ID,
        chama_id=CHAMA_ID,
        provider_code=provider_code,
        environment=environment,
        status=PaymentConnectionStatus.ACTIVE,
        credential_version=1,
    )


def attempt_request(
    *, amount: str = "500", phone: str = "+254712345678", ref: str = "ORD-1", charge: str = "CHA-1",
) -> PaymentAttemptRequest:
    return PaymentAttemptRequest(
        amount=Decimal(amount),
        currency="KES",
        customer_phone=phone,
        client_reference=ref,
        charge_reference=charge,
        callback_url="https://acme.example/cb",
    )


def jenga_credentials(**overrides) -> dict:
    creds = {
        "api_key": "api-key-1",
        "merchant_code": "MERCH001",
        "consumer_secret": "consumer-secret-1",
    }
    creds.update(overrides)
    return creds


def daraja_credentials(**overrides) -> dict:
    creds = {
        "consumer_key": "ck-1",
        "consumer_secret": "cs-1",
        "short_code": "174379",
        "passkey": "passkey-1",
    }
    creds.update(overrides)
    return creds


def jenga_handler(requests: list[httpx.Request], **responses) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = request.url.path
        if path == "/authentication/api/v3/authenticate/merchant":
            return responses.get(
                "auth", httpx.Response(200, json={"status": True, "token": "jwt-token"})
            )
        if path == "/api-checkout/mpesa-stk-push/v3.0/init":
            return responses.get(
                "init",
                httpx.Response(
                    200,
                    json={
                        "status": True,
                        "code": 0,
                        "data": {"orderReference": "ORD-1", "transactionId": "txn-1"},
                    },
                ),
            )
        if path.startswith("/api-checkout/mpesa-stk-push/v3.0/status/order/"):
            return responses.get(
                "status",
                httpx.Response(
                    200,
                    json={
                        "status": True,
                        "data": {
                            "order": {"orderStatus": "SUCCESS"},
                            "invoices": [{"externalReference": "ext-1"}],
                        },
                    },
                ),
            )
        raise AssertionError(f"Unexpected Jenga path {path}")

    return httpx.MockTransport(handler)


def daraja_handler(requests: list[httpx.Request], **responses) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = request.url.path
        if path == "/oauth/v1/generate":
            return responses.get(
                "oauth", httpx.Response(200, json={"access_token": "oauth-token"})
            )
        if path == "/mpesa/stkpush/v1/processrequest":
            return responses.get(
                "init",
                httpx.Response(
                    200,
                    json={
                        "ResponseCode": "0",
                        "CheckoutRequestID": "checkout-1",
                        "MerchantRequestID": "merchant-1",
                    },
                ),
            )
        if path == "/mpesa/stkpushquery/v1/query":
            return responses.get(
                "query",
                httpx.Response(
                    200,
                    json={
                        "ResultCode": "0",
                        "ResultDesc": "The service request is processed successfully.",
                        "CallbackMetadata": {
                            "Item": [{"Name": "MpesaReceiptNumber", "Value": "PBCA1X"}]
                        },
                    },
                ),
            )
        raise AssertionError(f"Unexpected Daraja path {path}")

    return httpx.MockTransport(handler)


def injected_client(transport: httpx.MockTransport, base_url: str) -> httpx.Client:
    return httpx.Client(transport=transport, base_url=base_url)


def extract_json(request: httpx.Request) -> dict:
    return json.loads(request.content.decode("utf-8"))


class TestRegistry:
    @pytest.mark.skip(reason="Jenga deferred; Daraja-only focus")
    def test_jenga_adapters_one_per_environment(self):
        adapters = create_jenga_adapters()
        assert len(adapters) == 2
        assert {a.environment for a in adapters} == {
            PaymentEnvironment.SANDBOX,
            PaymentEnvironment.PRODUCTION,
        }

    def test_daraja_adapters_one_per_environment(self):
        adapters = create_daraja_adapters()
        assert len(adapters) == 2
        assert {a.environment for a in adapters} == {
            PaymentEnvironment.SANDBOX,
            PaymentEnvironment.PRODUCTION,
        }

    @pytest.mark.parametrize(
        "adapter,code,capabilities",
        [
            (
                DarajaAdapter(PaymentEnvironment.SANDBOX),
                PaymentProviderCode.DARAJA,
                {"STK_PUSH", "PAYMENT_STATUS_QUERY", "CALLBACKS"},
            ),
        ],
    )
    def test_spec_metadata(self, adapter, code, capabilities):
        spec = adapter.spec
        assert spec.code == code
        assert spec.name
        assert all(spec.supports(cap) for cap in capabilities)


@pytest.mark.skip(reason="Jenga deferred; Daraja-only focus")
class TestJengaAuthentication:
    def test_access_token_request_contract(self):
        requests: list[httpx.Request] = []
        client = injected_client(jenga_handler(requests), JENGA_SANDBOX)
        adapter = JengaAdapter(PaymentEnvironment.SANDBOX, http_client=client)
        result = adapter.validate_credentials(
            credentials=jenga_credentials(), context=context(PaymentProviderCode.JENGA)
        )

        assert result.valid is True
        assert result.masked_account_identifier == "****H001"
        (req,) = requests
        assert req.url.path == "/authentication/api/v3/authenticate/merchant"
        assert req.method == "POST"
        assert req.headers["Api-Key"] == "api-key-1"
        assert extract_json(req) == {
            "merchantCode": "MERCH001",
            "consumerSecret": "consumer-secret-1",
        }

    def test_rejected_credentials_reported_as_auth_failed(self):
        requests: list[httpx.Request] = []
        client = injected_client(
            jenga_handler(
                requests,
                auth=httpx.Response(200, json={"status": False, "message": "bad login"}),
            ),
            JENGA_SANDBOX,
        )
        adapter = JengaAdapter(PaymentEnvironment.SANDBOX, http_client=client)
        result = adapter.validate_credentials(
            credentials=jenga_credentials(), context=context(PaymentProviderCode.JENGA)
        )
        assert result.valid is False
        assert result.error_code == "AUTH_FAILED"

    def test_missing_token_reported_invalid(self):
        requests: list[httpx.Request] = []
        client = injected_client(
            jenga_handler(requests, auth=httpx.Response(200, json={"status": True})),
            JENGA_SANDBOX,
        )
        adapter = JengaAdapter(PaymentEnvironment.SANDBOX, http_client=client)
        result = adapter.validate_credentials(
            credentials=jenga_credentials(), context=context(PaymentProviderCode.JENGA)
        )
        assert result.valid is False
        assert result.error_code == "AUTH_FAILED"

    def test_rejects_unknown_credential_fields(self):
        adapter = JengaAdapter(PaymentEnvironment.SANDBOX)
        with pytest.raises(ProviderIntegrationError) as excinfo:
            adapter.decrypted_credentials(
                jenga_credentials(extra="nope"), context(PaymentProviderCode.JENGA)
            )
        assert excinfo.value.code == "CREDENTIALS_UNEXPECTED"

    def test_rejects_incomplete_credentials(self):
        adapter = JengaAdapter(PaymentEnvironment.SANDBOX)
        with pytest.raises(ProviderIntegrationError) as excinfo:
            adapter.decrypted_credentials(
                {"api_key": "k"}, context(PaymentProviderCode.JENGA)
            )
        assert excinfo.value.code == "CREDENTIALS_INCOMPLETE"


class TestDarajaAuthentication:
    def test_oauth_request_contract(self):
        requests: list[httpx.Request] = []
        client = injected_client(daraja_handler(requests), DARAJA_SANDBOX)
        adapter = DarajaAdapter(PaymentEnvironment.SANDBOX, http_client=client)
        result = adapter.validate_credentials(
            credentials=daraja_credentials(), context=context(PaymentProviderCode.DARAJA)
        )

        assert result.valid is True
        assert result.masked_account_identifier == "****4379"
        (req,) = requests
        assert req.method == "GET"
        assert req.url.path == "/oauth/v1/generate"
        assert req.url.params["grant_type"] == "client_credentials"
        encoded = req.headers["Authorization"].split(" ")[1]
        assert base64.b64decode(encoded).decode() == "ck-1:cs-1"

    def test_rejected_credentials_reported_as_auth_failed(self):
        requests: list[httpx.Request] = []
        client = injected_client(
            daraja_handler(
                requests, oauth=httpx.Response(401, json={"errorMessage": "bad auth"})
            ),
            DARAJA_SANDBOX,
        )
        adapter = DarajaAdapter(PaymentEnvironment.SANDBOX, http_client=client)
        result = adapter.validate_credentials(
            credentials=daraja_credentials(), context=context(PaymentProviderCode.DARAJA)
        )
        assert result.valid is False
        assert result.error_code == "AUTH_FAILED"

    def test_missing_access_token_reported_invalid(self):
        requests: list[httpx.Request] = []
        client = injected_client(
            daraja_handler(requests, oauth=httpx.Response(200, json={})), DARAJA_SANDBOX
        )
        adapter = DarajaAdapter(PaymentEnvironment.SANDBOX, http_client=client)
        result = adapter.validate_credentials(
            credentials=daraja_credentials(), context=context(PaymentProviderCode.DARAJA)
        )
        assert result.valid is False
        assert result.error_code == "AUTH_FAILED"


@pytest.mark.skip(reason="Jenga deferred; Daraja-only focus")
class TestJengaPaymentAttempt:
    def test_stk_push_request_contract(self):
        requests: list[httpx.Request] = []
        client = injected_client(jenga_handler(requests), JENGA_SANDBOX)
        adapter = JengaAdapter(PaymentEnvironment.SANDBOX, http_client=client)

        result = adapter.create_payment_attempt(
            credentials=jenga_credentials(),
            request=attempt_request(ref="ORD-1", charge="CHA-1"),
            context=context(PaymentProviderCode.JENGA),
        )

        assert result.accepted is True
        assert result.provider_request_id == "ORD-1"
        assert result.provider_transaction_id == "txn-1"
        assert result.normalized_status == ProviderTransactionStatus.PENDING

        (_, init_req) = requests
        assert init_req.method == "POST"
        assert init_req.url.path == "/api-checkout/mpesa-stk-push/v3.0/init"
        assert init_req.headers["Authorization"] == "Bearer jwt-token"
        body = extract_json(init_req)
        assert body["order"]["orderReference"] == "ORD-1"
        assert body["order"]["orderAmount"] == "500"
        assert body["order"]["orderCurrency"] == "KES"
        assert body["payment"]["callbackUrl"] == "https://acme.example/cb"
        assert body["customer"]["phoneNumber"] == "254712345678"
        assert body["payment"]["details"]["msisdn"] == "254712345678"
        assert "Signature" not in init_req.headers

    def test_falls_back_to_client_reference_when_no_order_reference(self):
        requests: list[httpx.Request] = []
        client = injected_client(
            jenga_handler(
                requests,
                init=httpx.Response(200, json={"status": True, "code": 0, "data": {}}),
            ),
            JENGA_SANDBOX,
        )
        adapter = JengaAdapter(PaymentEnvironment.SANDBOX, http_client=client)
        result = adapter.create_payment_attempt(
            credentials=jenga_credentials(),
            request=attempt_request(ref="ORD-1"),
            context=context(PaymentProviderCode.JENGA),
        )
        assert result.accepted is True
        assert result.provider_request_id == "ORD-1"

    def test_rejected_response_maps_to_failed_result(self):
        requests: list[httpx.Request] = []
        client = injected_client(
            jenga_handler(
                requests,
                init=httpx.Response(
                    200, json={"status": False, "code": 500, "message": "no funds"}
                ),
            ),
            JENGA_SANDBOX,
        )
        adapter = JengaAdapter(PaymentEnvironment.SANDBOX, http_client=client)
        result = adapter.create_payment_attempt(
            credentials=jenga_credentials(),
            request=attempt_request(),
            context=context(PaymentProviderCode.JENGA),
        )
        assert result.accepted is False
        assert result.normalized_status == ProviderTransactionStatus.FAILED
        assert result.error_code == "JENGA_500"
        assert result.retryable is False

    def test_phone_normalization(self):
        requests: list[httpx.Request] = []
        client = injected_client(jenga_handler(requests), JENGA_SANDBOX)
        adapter = JengaAdapter(PaymentEnvironment.SANDBOX, http_client=client)
        ok = adapter.create_payment_attempt(
            credentials=jenga_credentials(),
            request=attempt_request(phone="0712345678"),
            context=context(PaymentProviderCode.JENGA),
        )
        assert ok.accepted is True
        for req in requests:
            if req.url.path.endswith("/init"):
                assert extract_json(req)["customer"]["phoneNumber"] == "254712345678"

    def test_invalid_phone_rejected(self):
        requests: list[httpx.Request] = []
        client = injected_client(jenga_handler(requests), JENGA_SANDBOX)
        adapter = JengaAdapter(PaymentEnvironment.SANDBOX, http_client=client)
        with pytest.raises(ProviderIntegrationError) as excinfo:
            adapter.create_payment_attempt(
                credentials=jenga_credentials(),
                request=attempt_request(phone="0712345"),
                context=context(PaymentProviderCode.JENGA),
            )
        assert excinfo.value.code == "PHONE_FORMAT"


@pytest.mark.skip(reason="Jenga deferred; Daraja-only focus")
class TestJengaSignature:
    @staticmethod
    def _rsa_key_pair():
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
        pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("ascii")
        return key, pem

    def test_signature_header_uses_documented_canonical_string(self):
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        private_key, pem = self._rsa_key_pair()
        requests: list[httpx.Request] = []
        client = injected_client(jenga_handler(requests), JENGA_SANDBOX)
        adapter = JengaAdapter(PaymentEnvironment.SANDBOX, http_client=client)

        adapter.create_payment_attempt(
            credentials=jenga_credentials(signing_private_key=pem),
            request=attempt_request(ref="ORD-SIG", phone="+254700111222"),
            context=context(PaymentProviderCode.JENGA),
        )
        req = [r for r in requests if r.url.path.endswith("/init")][0]
        signature = req.headers.get("Signature")
        assert signature

        body = extract_json(req)
        canonical = "".join(
            [
                body["order"]["orderReference"],
                body["order"]["orderAmount"],
                body["order"]["orderCurrency"],
                body["customer"]["phoneNumber"],
                str(body["payment"]["details"]["paymentAmount"]),
                body["payment"]["paymentCurrency"],
            ]
        )
        public_key = private_key.public_key()
        public_key.verify(
            base64.b64decode(signature),
            canonical.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )

    def test_signature_omitted_when_disabled(self):
        _, pem = self._rsa_key_pair()
        requests: list[httpx.Request] = []
        client = injected_client(jenga_handler(requests), JENGA_SANDBOX)
        adapter = JengaAdapter(
            PaymentEnvironment.SANDBOX, http_client=client, attempt_signature=False
        )
        adapter.create_payment_attempt(
            credentials=jenga_credentials(signing_private_key=pem),
            request=attempt_request(),
            context=context(PaymentProviderCode.JENGA),
        )
        req = [r for r in requests if r.url.path.endswith("/init")][0]
        assert "Signature" not in req.headers

    def test_invalid_signing_key_raises(self):
        requests: list[httpx.Request] = []
        client = injected_client(jenga_handler(requests), JENGA_SANDBOX)
        adapter = JengaAdapter(PaymentEnvironment.SANDBOX, http_client=client)
        with pytest.raises(ProviderIntegrationError) as excinfo:
            adapter.create_payment_attempt(
                credentials=jenga_credentials(signing_private_key="not a pem"),
                request=attempt_request(),
                context=context(PaymentProviderCode.JENGA),
            )
        assert excinfo.value.code == "SIGNING_KEY_INVALID"


class TestDarajaPaymentAttempt:
    def test_stk_push_request_contract(self):
        requests: list[httpx.Request] = []
        client = injected_client(daraja_handler(requests), DARAJA_SANDBOX)
        adapter = DarajaAdapter(PaymentEnvironment.SANDBOX, http_client=client)

        result = adapter.create_payment_attempt(
            credentials=daraja_credentials(),
            request=attempt_request(ref="REF-ABC-123", charge="CHARGE-ABC-456"),
            context=context(PaymentProviderCode.DARAJA),
        )

        assert result.accepted is True
        assert result.provider_request_id == "checkout-1"
        assert result.provider_transaction_id == "merchant-1"
        assert result.normalized_status == ProviderTransactionStatus.PENDING

        (_, init_req) = requests
        assert init_req.method == "POST"
        assert init_req.url.path == "/mpesa/stkpush/v1/processrequest"
        assert init_req.headers["Authorization"] == "Bearer oauth-token"
        body = extract_json(init_req)
        assert body["BusinessShortCode"] == "174379"
        assert body["TransactionType"] == "CustomerPayBillOnline"
        assert body["Amount"] == "500"
        assert body["PartyA"] == "254712345678"
        assert body["PartyB"] == "174379"
        assert body["CallBackURL"] == "https://acme.example/cb"
        assert body["AccountReference"] == "CHARGE-ABC-4"
        assert body["TransactionDesc"] == "REF-ABC-123"
        password = base64.b64decode(body["Password"]).decode("utf-8")
        assert password.startswith("174379")
        assert "passkey-1" in password
        timestamp = re.search(r"\d{14}$", password)
        assert timestamp
        assert body["Timestamp"] == timestamp.group(0)

    def test_whole_kes_amount_required(self):
        requests: list[httpx.Request] = []
        client = injected_client(daraja_handler(requests), DARAJA_SANDBOX)
        adapter = DarajaAdapter(PaymentEnvironment.SANDBOX, http_client=client)
        with pytest.raises(ProviderIntegrationError) as excinfo:
            adapter.create_payment_attempt(
                credentials=daraja_credentials(),
                request=attempt_request(amount="500.50"),
                context=context(PaymentProviderCode.DARAJA),
            )
        assert excinfo.value.code == "AMOUNT_NOT_INTEGER"

    def test_rejected_response_maps_to_failed_result(self):
        requests: list[httpx.Request] = []
        client = injected_client(
            daraja_handler(
                requests,
                init=httpx.Response(
                    200,
                    json={"ResponseCode": "1", "ResponseDescription": "insufficient balance"},
                ),
            ),
            DARAJA_SANDBOX,
        )
        adapter = DarajaAdapter(PaymentEnvironment.SANDBOX, http_client=client)
        result = adapter.create_payment_attempt(
            credentials=daraja_credentials(),
            request=attempt_request(),
            context=context(PaymentProviderCode.DARAJA),
        )
        assert result.accepted is False
        assert result.normalized_status == ProviderTransactionStatus.FAILED
        assert result.error_code == "DARAJA_1"
        assert result.retryable is False


@pytest.mark.skip(reason="Jenga deferred; Daraja-only focus")
class TestJengaStatusQuery:
    def test_status_query_contract(self):
        requests: list[httpx.Request] = []
        client = injected_client(jenga_handler(requests), JENGA_SANDBOX)
        adapter = JengaAdapter(PaymentEnvironment.SANDBOX, http_client=client)
        result = adapter.query_payment_status(
            credentials=jenga_credentials(),
            provider_request_id="ORD-1",
            client_reference="ORD-1",
            context=context(PaymentProviderCode.JENGA),
        )
        assert result.found is True
        assert result.normalized_status == ProviderTransactionStatus.SUCCEEDED
        assert result.provider_transaction_id == "ext-1"
        query_req = requests[-1]
        assert query_req.method == "GET"
        assert query_req.url.path == "/api-checkout/mpesa-stk-push/v3.0/status/order/ORD-1"

    def test_status_falls_back_to_client_reference(self):
        requests: list[httpx.Request] = []
        client = injected_client(jenga_handler(requests), JENGA_SANDBOX)
        adapter = JengaAdapter(PaymentEnvironment.SANDBOX, http_client=client)
        adapter.query_payment_status(
            credentials=jenga_credentials(),
            provider_request_id=None,
            client_reference="CLI-REF",
            context=context(PaymentProviderCode.JENGA),
        )
        assert requests[-1].url.path.endswith("/status/order/CLI-REF")

    def test_order_not_found(self):
        requests: list[httpx.Request] = []
        client = injected_client(
            jenga_handler(
                requests,
                status=httpx.Response(
                    200, json={"status": False, "message": "order not found"}
                ),
            ),
            JENGA_SANDBOX,
        )
        adapter = JengaAdapter(PaymentEnvironment.SANDBOX, http_client=client)
        result = adapter.query_payment_status(
            credentials=jenga_credentials(),
            provider_request_id="ORD-X",
            client_reference="ORD-X",
            context=context(PaymentProviderCode.JENGA),
        )
        assert result.found is False
        assert result.normalized_status == ProviderTransactionStatus.UNKNOWN
        assert result.error_code == "JENGA_NOT_FOUND"

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("SUCCESS", ProviderTransactionStatus.SUCCEEDED),
            ("PAID", ProviderTransactionStatus.SUCCEEDED),
            ("FAILED", ProviderTransactionStatus.FAILED),
            ("CANCELLED", ProviderTransactionStatus.FAILED),
            ("-1", ProviderTransactionStatus.UNKNOWN),
            ("anything", ProviderTransactionStatus.UNKNOWN),
        ],
    )
    def test_normalize_provider_status(self, raw, expected):
        adapter = JengaAdapter(PaymentEnvironment.SANDBOX)
        assert adapter.normalize_provider_status(raw) == expected


class TestDarajaStatusQuery:
    def test_successful_query_contract(self):
        requests: list[httpx.Request] = []
        client = injected_client(daraja_handler(requests), DARAJA_SANDBOX)
        adapter = DarajaAdapter(PaymentEnvironment.SANDBOX, http_client=client)
        result = adapter.query_payment_status(
            credentials=daraja_credentials(),
            provider_request_id="checkout-1",
            client_reference="ORD-1",
            context=context(PaymentProviderCode.DARAJA),
        )
        assert result.found is True
        assert result.normalized_status == ProviderTransactionStatus.SUCCEEDED
        assert result.provider_transaction_id == "PBCA1X"
        assert requests[-1].method == "POST"
        assert requests[-1].url.path == "/mpesa/stkpushquery/v1/query"
        body = extract_json(requests[-1])
        assert body["CheckoutRequestID"] == "checkout-1"
        assert body["BusinessShortCode"] == "174379"

    def test_timeout_result_code_is_unknown(self):
        requests: list[httpx.Request] = []
        client = injected_client(
            daraja_handler(
                requests,
                query=httpx.Response(
                    200,
                    json={"ResultCode": "1037", "ResultDesc": "Request cancelled by user"},
                ),
            ),
            DARAJA_SANDBOX,
        )
        adapter = DarajaAdapter(PaymentEnvironment.SANDBOX, http_client=client)
        result = adapter.query_payment_status(
            credentials=daraja_credentials(),
            provider_request_id="checkout-1",
            client_reference="ORD-1",
            context=context(PaymentProviderCode.DARAJA),
        )
        assert result.normalized_status == ProviderTransactionStatus.UNKNOWN

    def test_failure_result_code(self):
        requests: list[httpx.Request] = []
        client = injected_client(
            daraja_handler(
                requests,
                query=httpx.Response(
                    200,
                    json={"ResultCode": "2001", "ResultDesc": "invalid transaction"},
                ),
            ),
            DARAJA_SANDBOX,
        )
        adapter = DarajaAdapter(PaymentEnvironment.SANDBOX, http_client=client)
        result = adapter.query_payment_status(
            credentials=daraja_credentials(),
            provider_request_id="checkout-1",
            client_reference="ORD-1",
            context=context(PaymentProviderCode.DARAJA),
        )
        assert result.normalized_status == ProviderTransactionStatus.FAILED
        assert result.error_code == "DARAJA_2001"

    def test_query_without_order_reference_rejected(self):
        adapter = DarajaAdapter(PaymentEnvironment.SANDBOX)
        with pytest.raises(ProviderIntegrationError) as excinfo:
            adapter.query_payment_status(
                credentials=daraja_credentials(),
                provider_request_id=None,
                client_reference="ORD-1",
                context=context(PaymentProviderCode.DARAJA),
            )
        assert excinfo.value.code == "QUERY_REFERENCE_MISSING"


@pytest.mark.skip(reason="Jenga deferred; Daraja-only focus")
class TestJengaCallbacks:
    def test_parse_success_callback(self):
        adapter = JengaAdapter(PaymentEnvironment.SANDBOX)
        raw = {
            "orderReference": "ORD-1",
            "paymentReference": "payment-ref-1",
            "transactionId": "txn-123",
            "status": "SUCCESS",
            "amount": "500.00",
            "currency": "KES",
            "phoneNumber": "+254712345678",
        }
        parsed = adapter.parse_callback(
            raw_payload=json.dumps(raw).encode("utf-8")
        )
        assert parsed.is_parseable is True
        assert parsed.provider_event_id == "txn-123"
        assert parsed.provider_request_id == "ORD-1"
        assert parsed.amount == Decimal("500.00")
        assert parsed.currency == "KES"
        assert parsed.normalized_status == ProviderTransactionStatus.SUCCEEDED

    def test_unparseable_callback(self):
        adapter = JengaAdapter(PaymentEnvironment.SANDBOX)
        parsed = adapter.parse_callback(raw_payload=b"not json")
        assert parsed.is_parseable is False
        assert parsed.provider_event_id is None

    def test_missing_event_id_unparseable(self):
        adapter = JengaAdapter(PaymentEnvironment.SANDBOX)
        parsed = adapter.parse_callback(
            raw_payload=json.dumps({"status": "SUCCESS"}).encode("utf-8")
        )
        assert parsed.is_parseable is False

    def test_verify_callback_is_documented_pass_through(self):
        adapter = JengaAdapter(PaymentEnvironment.SANDBOX)
        ok, reason = adapter.verify_callback(
            raw_payload=b"{}", headers={"Host": "acme.example"}
        )
        assert ok is True
        assert reason is None


class TestDarajaCallbacks:
    def test_parse_success_callback(self):
        adapter = DarajaAdapter(PaymentEnvironment.SANDBOX)
        raw = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "merchant-1",
                    "CheckoutRequestID": "ws_CO_1234_5678",
                    "ResultCode": 0,
                    "ResultDesc": "The service request is processed successfully.",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 500.0},
                            {"Name": "MpesaReceiptNumber", "Value": "PBCA1ABCDEF"},
                            {"Name": "PhoneNumber", "Value": 254712345678},
                        ]
                    },
                }
            }
        }
        parsed = adapter.parse_callback(raw_payload=json.dumps(raw).encode("utf-8"))
        assert parsed.is_parseable is True
        assert parsed.provider_event_id == "ws_CO_1234_5678"
        assert parsed.provider_request_id == "ws_CO_1234_5678"
        assert parsed.provider_transaction_id == "PBCA1ABCDEF"
        assert parsed.amount == Decimal("500")
        assert parsed.payer_phone == "254712345678"
        assert parsed.normalized_status == ProviderTransactionStatus.SUCCEEDED

    def test_parse_failure_callback(self):
        adapter = DarajaAdapter(PaymentEnvironment.SANDBOX)
        raw = {
            "Body": {
                "stkCallback": {
                    "CheckoutRequestID": "ws_CO_1234_5678",
                    "ResultCode": 1032,
                    "ResultDesc": "Request cancelled by user",
                }
            }
        }
        parsed = adapter.parse_callback(raw_payload=json.dumps(raw).encode("utf-8"))
        assert parsed.is_parseable is True
        assert parsed.normalized_status == ProviderTransactionStatus.FAILED
        assert parsed.error_code == "DARAJA_1032"

    def test_unparseable_callback(self):
        adapter = DarajaAdapter(PaymentEnvironment.SANDBOX)
        parsed = adapter.parse_callback(raw_payload=b"{}")
        assert parsed.is_parseable is False

    def test_verify_callback_is_documented_pass_through(self):
        adapter = DarajaAdapter(PaymentEnvironment.SANDBOX)
        ok, reason = adapter.verify_callback(raw_payload=b"{}", headers={"Host": "x"})
        assert ok is True
        assert reason is None

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("0", ProviderTransactionStatus.SUCCEEDED),
            ("1", ProviderTransactionStatus.FAILED),
            ("1032", ProviderTransactionStatus.FAILED),
            ("1037", ProviderTransactionStatus.FAILED),
            ("", ProviderTransactionStatus.UNKNOWN),
            ("unknown", ProviderTransactionStatus.UNKNOWN),
        ],
    )
    def test_normalize_provider_status(self, raw, expected):
        adapter = DarajaAdapter(PaymentEnvironment.SANDBOX)
        assert adapter.normalize_provider_status(raw) == expected

    def test_phone_normalization_helper(self):
        from app.providers.daraja.adapter import normalize_phone

        assert normalize_phone("0712345678") == "254712345678"
        assert normalize_phone("+254712345678") == "254712345678"
        with pytest.raises(ProviderIntegrationError) as excinfo:
            normalize_phone("12345")
        assert excinfo.value.code == "PHONE_FORMAT"


class TestHttpErrorMapping:
    def test_timeout_maps_to_provider_timeout_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout("timed out", request=request)

        client = httpx.Client(
            transport=httpx.MockTransport(handler), base_url=JENGA_SANDBOX
        )
        http = ProviderHttpClient(JENGA_SANDBOX)
        http._client = client
        with pytest.raises(ProviderTimeoutError) as excinfo:
            http.request("GET", "/anything")
        assert excinfo.value.code == "PROVIDER_TIMEOUT"

    def test_connect_error_maps_to_integration_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused", request=request)

        client = httpx.Client(
            transport=httpx.MockTransport(handler), base_url=JENGA_SANDBOX
        )
        http = ProviderHttpClient(JENGA_SANDBOX)
        http._client = client
        with pytest.raises(ProviderIntegrationError) as excinfo:
            http.request("GET", "/anything")
        assert excinfo.value.code == "PROVIDER_UNREACHABLE"