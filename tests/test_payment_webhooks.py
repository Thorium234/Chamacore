"""Webhook event inbox API and service tests (ADR-018)."""

import json
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.callback_utils import connection_callback_token
from app.models.enums import (
    PaymentEnvironment,
    PaymentEventStatus,
    PaymentProviderCode,
    ProviderTransactionStatus,
)
from app.models.payment_event import PaymentEvent
from tests.conftest import add_membership, create_chama, register_and_login
from tests.fake_provider import (
    FakeAdapter,
    PaymentAttemptResult,
    StatusQueryResult,
    setup_fake_adapter,
    restore_fake_adapter,
)
from tests.fake_provider import ProviderTransactionStatus as _PTS

JENGA = PaymentProviderCode.JENGA.value
SANDBOX = PaymentEnvironment.SANDBOX.value


@pytest.fixture()
def fake_jenga():
    fake = setup_fake_adapter(PaymentProviderCode.JENGA, PaymentEnvironment.SANDBOX)
    try:
        yield fake
    finally:
        restore_fake_adapter(PaymentProviderCode.JENGA, PaymentEnvironment.SANDBOX)


def _chair(client):
    return register_and_login(client, "chair@e.com")


def _setup(client, fake_jenga):
    headers = _chair(client)
    chama = create_chama(client, headers)
    member = add_membership(
        client, headers, chama["id"],
        phone="+254700000099", govt="GID-099",
    )
    r = client.post(
        f"/api/v1/chamas/{chama['id']}/payment-connections",
        headers=headers,
        json={
            "provider_code": JENGA,
            "environment": SANDBOX,
            "credentials": {
                "api_key": "ak_123",
                "merchant_code": "M1001",
                "consumer_secret": "cs_secret_value",
            },
        },
    )
    assert r.status_code == 201
    conn = r.json()
    r = client.post(
        f"/api/v1/chamas/{chama['id']}/payment-connections/{conn['id']}/validate",
        headers=headers,
    )
    assert r.status_code == 200
    intent = client.post(
        f"/api/v1/chamas/{chama['id']}/payment-intents",
        headers=headers,
        json={
            "membership_id": member["id"],
            "amount": "50.00",
            "currency": "KES",
            "purpose": "monthly contribution",
            "idempotency_key": "webhook-test-1",
        },
    ).json()
    attempt = client.post(
        f"/api/v1/chamas/{chama['id']}/payment-intents/{intent['id']}/initiate",
        headers=headers,
        json={"connection_id": conn["id"]},
    ).json()
    return headers, chama, member, conn, intent, attempt


def _callback_url(conn: dict) -> str:
    token = connection_callback_token(
        connection_id=uuid.UUID(conn["id"]),
        provider_code=PaymentProviderCode(conn["provider_code"]),
        environment=PaymentEnvironment(conn["environment"]),
    )
    return (
        f"/api/v1/payments/webhooks/{conn['provider_code']}/{conn['environment']}"
        f"?connection_id={conn['id']}&token={token}"
    )


def _webhook_payload(
    *,
    provider_event_id="EVT-001",
    provider_request_id=None,
    provider_transaction_id="TXN-001",
    amount="50.00",
    currency="KES",
    normalized_status="SUCCEEDED",
) -> dict:
    return {
        "provider_event_id": provider_event_id,
        "provider_request_id": provider_event_id if provider_request_id is None else provider_request_id,
        "provider_transaction_id": provider_transaction_id,
        "amount": amount,
        "currency": currency,
        "normalized_status": normalized_status,
    }


class TestWebhookSuccess:
    def test_valid_callback_succeeds(self, client, fake_jenga, db):
        headers, chama, member, conn, intent, attempt = _setup(client, fake_jenga)
        url = _callback_url(conn)
        body = _webhook_payload(provider_request_id=attempt["provider_request_id"])
        r = client.post(url, content=json.dumps(body).encode(), headers={"content-type": "application/json"})
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["event_status"] == "PROCESSED"
        event = db.get(PaymentEvent, uuid.UUID(data["event_id"]))
        assert event is not None
        assert event.status == PaymentEventStatus.PROCESSED

    def test_callback_advances_intent_to_succeeded(self, client, fake_jenga, db):
        headers, chama, member, conn, intent, attempt = _setup(client, fake_jenga)
        url = _callback_url(conn)
        body = _webhook_payload(provider_request_id=attempt["provider_request_id"])
        client.post(url, content=json.dumps(body).encode(), headers={"content-type": "application/json"})
        from app.models.payment_intent import PaymentIntent
        row = db.scalar(select(PaymentIntent).where(PaymentIntent.id == uuid.UUID(intent["id"])))
        assert row.status.value == "SUCCEEDED"
        from app.models.payment_attempt import PaymentAttempt
        att = db.scalar(select(PaymentAttempt).where(PaymentAttempt.id == uuid.UUID(attempt["id"])))
        assert att.status.value == "SUCCEEDED"


class TestWebhookDedup:
    def test_duplicate_event_is_deduplicated(self, client, fake_jenga):
        headers, chama, member, conn, intent, attempt = _setup(client, fake_jenga)
        url = _callback_url(conn)
        body = _webhook_payload(provider_request_id=attempt["provider_request_id"])
        first = client.post(url, content=json.dumps(body).encode(), headers={"content-type": "application/json"}).json()
        assert first["event_status"] == "PROCESSED"
        second = client.post(url, content=json.dumps(body).encode(), headers={"content-type": "application/json"}).json()
        assert second["event_status"] == "DEDUPLICATED"

    def test_same_event_id_different_payload_disagrees(self, client, fake_jenga):
        headers, chama, member, conn, intent, attempt = _setup(client, fake_jenga)
        url = _callback_url(conn)
        body1 = _webhook_payload(
            provider_event_id="EVT-SAME",
            provider_request_id=attempt["provider_request_id"],
            amount="50.00",
        )
        client.post(url, content=json.dumps(body1).encode(), headers={"content-type": "application/json"})
        body2 = _webhook_payload(
            provider_event_id="EVT-SAME",
            provider_request_id=attempt["provider_request_id"],
            amount="999.00",
        )
        r = client.post(url, content=json.dumps(body2).encode(), headers={"content-type": "application/json"})
        assert r.json()["event_status"] == "DISAGREEMENT"


class TestWebhookVerification:
    def test_verification_failure_rejected(self, client, fake_jenga):
        headers, chama, member, conn, intent, attempt = _setup(client, fake_jenga)
        fake_jenga.verify_result = (False, "bad signature")
        url = _callback_url(conn)
        body = _webhook_payload(provider_request_id=attempt["provider_request_id"])
        r = client.post(url, content=json.dumps(body).encode(), headers={"content-type": "application/json"})
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "WEBHOOK_REJECTED"


class TestWebhookAmountMatch:
    def test_amount_mismatch_is_disagreement(self, client, fake_jenga):
        headers, chama, member, conn, intent, attempt = _setup(client, fake_jenga)
        url = _callback_url(conn)
        body = _webhook_payload(
            provider_event_id="EVT-AMT",
            provider_request_id=attempt["provider_request_id"],
            amount="999.00",
        )
        r = client.post(url, content=json.dumps(body).encode(), headers={"content-type": "application/json"})
        assert r.json()["event_status"] == "DISAGREEMENT"

    def test_currency_mismatch_is_disagreement(self, client, fake_jenga):
        headers, chama, member, conn, intent, attempt = _setup(client, fake_jenga)
        url = _callback_url(conn)
        body = _webhook_payload(
            provider_event_id="EVT-CUR",
            provider_request_id=attempt["provider_request_id"],
            currency="USD",
        )
        r = client.post(url, content=json.dumps(body).encode(), headers={"content-type": "application/json"})
        assert r.json()["event_status"] == "DISAGREEMENT"


class TestWebhookToken:
    def test_missing_token_with_valid_request_id_falls_back(self, client, fake_jenga):
        headers, chama, member, conn, intent, attempt = _setup(client, fake_jenga)
        url = f"/api/v1/payments/webhooks/{conn['provider_code']}/{conn['environment']}?connection_id={conn['id']}"
        body = _webhook_payload(provider_request_id=attempt["provider_request_id"])
        r = client.post(url, content=json.dumps(body).encode(), headers={"content-type": "application/json"})
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_invalid_token_rejected(self, client, fake_jenga):
        headers, chama, member, conn, intent, attempt = _setup(client, fake_jenga)
        url = (
            f"/api/v1/payments/webhooks/{conn['provider_code']}/{conn['environment']}"
            f"?connection_id={conn['id']}&token=invalid-token"
        )
        body = _webhook_payload(provider_request_id=attempt["provider_request_id"])
        r = client.post(url, content=json.dumps(body).encode(), headers={"content-type": "application/json"})
        assert r.status_code == 400
        assert "WEBHOOK_REJECTED" in r.json()["detail"]["code"]

    def test_nonexistent_connection_rejected(self, client, fake_jenga):
        headers, chama, member, conn, intent, attempt = _setup(client, fake_jenga)
        fake_id = str(uuid.uuid4())
        token = connection_callback_token(
            connection_id=uuid.UUID(fake_id),
            provider_code=PaymentProviderCode.JENGA,
            environment=PaymentEnvironment.SANDBOX,
        )
        url = f"/api/v1/payments/webhooks/JENGA/SANDBOX?connection_id={fake_id}&token={token}"
        body = _webhook_payload()
        r = client.post(url, content=json.dumps(body).encode(), headers={"content-type": "application/json"})
        assert r.status_code == 400


class TestWebhookFailedPayment:
    def test_failed_callback_on_first_attempt(self, client, fake_jenga, db):
        headers, chama, member, conn, intent, attempt = _setup(client, fake_jenga)
        url = _callback_url(conn)
        body = _webhook_payload(
            provider_event_id="EVT-FAIL",
            provider_request_id=attempt["provider_request_id"],
            normalized_status="FAILED",
        )
        r = client.post(url, content=json.dumps(body).encode(), headers={"content-type": "application/json"})
        assert r.json()["ok"] is True
        assert r.json()["event_status"] == "PROCESSED"
        from app.models.payment_intent import PaymentIntent
        intent_row = db.scalar(select(PaymentIntent).where(PaymentIntent.id == uuid.UUID(intent["id"])))
        assert intent_row.status.value == "PROCESSING"
        from app.models.payment_attempt import PaymentAttempt
        att_row = db.scalar(select(PaymentAttempt).where(PaymentAttempt.id == uuid.UUID(attempt["id"])))
        assert att_row.status.value == "FAILED"