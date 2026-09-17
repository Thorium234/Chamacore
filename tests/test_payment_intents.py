"""Payment intent create/idempotency/initiate orchestration tests (ADR-016)."""

import uuid

import pytest
from sqlalchemy import select

from app.models.enums import PaymentEnvironment, PaymentProviderCode
from app.models.payment_attempt import PaymentAttempt
from app.models.payment_intent import PaymentIntent
from app.models.provider_transaction import ProviderTransaction
from app.providers.errors import ProviderTimeoutError
from tests.conftest import add_membership, create_chama, register_and_login
from tests.fake_provider import (
    PaymentAttemptResult,
    ProviderTransactionStatus as _PTS,
    StatusQueryResult,
    setup_fake_adapter,
    restore_fake_adapter,
)

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


def _other(client, email="member@e.com"):
    return register_and_login(client, email)


def _scenario(client, fake_jenga):
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
    assert r.status_code == 201, r.json()
    conn = r.json()
    r = client.post(
        f"/api/v1/chamas/{chama['id']}/payment-connections/{conn['id']}/validate",
        headers=headers,
    )
    assert r.status_code == 200, r.json()
    assert r.json()["status"] == "ACTIVE"
    return headers, chama, member, r.json()


def _create_intent(client, headers, chama_id, member_id, *, key="key-1", amount="50.00"):
    r = client.post(
        f"/api/v1/chamas/{chama_id}/payment-intents",
        headers=headers,
        json={
            "membership_id": member_id,
            "amount": amount,
            "currency": "KES",
            "purpose": "monthly contribution",
            "idempotency_key": key,
        },
    )
    assert r.status_code == 201, r.json()
    return r.json()


def _initiate(client, headers, chama_id, intent_id, connection_id):
    return client.post(
        f"/api/v1/chamas/{chama_id}/payment-intents/{intent_id}/initiate",
        headers=headers,
        json={"connection_id": connection_id},
    )


def _attempt_reference(intent_id: str, number: int) -> str:
    return f"PAY-{uuid.UUID(intent_id).hex[:16]}-{number:02d}"


class TestCreateIntent:
    def test_create_intent(self, client, fake_jenga):
        headers, chama, member, conn = _scenario(client, fake_jenga)
        intent = _create_intent(client, headers, chama["id"], member["id"])
        assert intent["status"] == "PENDING"
        assert intent["idempotency_key"] == "key-1"
        assert intent["currency"] == "KES"

    def test_idempotent_create_returns_same_intent(self, client, fake_jenga):
        headers, chama, member, conn = _scenario(client, fake_jenga)
        first = _create_intent(client, headers, chama["id"], member["id"])
        second = _create_intent(client, headers, chama["id"], member["id"])
        assert second["id"] == first["id"]
        assert second["amount"] == first["amount"]

    def test_same_key_different_amount_conflicts(self, client, fake_jenga):
        headers, chama, member, conn = _scenario(client, fake_jenga)
        _create_intent(client, headers, chama["id"], member["id"])
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payment-intents",
            headers=headers,
            json={
                "membership_id": member["id"],
                "amount": "999.00",
                "currency": "KES",
                "purpose": "different",
                "idempotency_key": "key-1",
            },
        )
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "CONFLICT"

    def test_same_key_different_membership_conflicts(self, client, fake_jenga):
        headers, chama, member, conn = _scenario(client, fake_jenga)
        second_member = add_membership(
            client, headers, chama["id"],
            phone="+254700000101", govt="GID-101",
        )
        _create_intent(client, headers, chama["id"], member["id"])
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payment-intents",
            headers=headers,
            json={
                "membership_id": second_member["id"],
                "amount": "50.00",
                "currency": "KES",
                "purpose": "monthly contribution",
                "idempotency_key": "key-1",
            },
        )
        assert r.status_code == 409

    def test_different_key_allows_separate_intent(self, client, fake_jenga):
        headers, chama, member, conn = _scenario(client, fake_jenga)
        first = _create_intent(client, headers, chama["id"], member["id"], key="key-1")
        second = _create_intent(client, headers, chama["id"], member["id"], key="key-2")
        assert second["id"] != first["id"]

    def test_non_member_cannot_create(self, client, fake_jenga):
        headers, chama, member, conn = _scenario(client, fake_jenga)
        outsider = _other(client, "outsider@e.com")
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payment-intents",
            headers=outsider,
            json={
                "membership_id": member["id"],
                "amount": "50.00",
                "currency": "KES",
                "purpose": "monthly contribution",
                "idempotency_key": "key-outsider",
            },
        )
        assert r.status_code == 403

    def test_inactive_target_membership_rejected(self, client, fake_jenga, db):
        headers, chama, member, conn = _scenario(client, fake_jenga)
        from app.models.enums import MembershipStatus

        from app.models.membership import Membership

        membership = db.get(Membership, uuid.UUID(member["id"]))
        membership.status = MembershipStatus.INACTIVE
        db.commit()
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payment-intents",
            headers=headers,
            json={
                "membership_id": member["id"],
                "amount": "50.00",
                "currency": "KES",
                "purpose": "monthly contribution",
                "idempotency_key": "key-inactive",
            },
        )
        assert r.status_code == 400


class TestInitiate:
    def test_initiate_creates_first_attempt(self, client, fake_jenga, db):
        headers, chama, member, conn = _scenario(client, fake_jenga)
        intent = _create_intent(client, headers, chama["id"], member["id"])
        r = _initiate(client, headers, chama["id"], intent["id"], conn["id"])
        assert r.status_code == 200, r.json()
        attempt = r.json()
        assert attempt["attempt_number"] == 1
        assert attempt["status"] == "INITIATED"
        assert attempt["provider_request_id"].startswith("REQ-")
        row = db.scalar(
            select(PaymentIntent).where(PaymentIntent.id == uuid.UUID(intent["id"]))
        )
        assert row.status.value == "PROCESSING"
        txn = db.scalar(
            select(ProviderTransaction).where(
                ProviderTransaction.payment_attempt_id == uuid.UUID(attempt["id"])
            )
        )
        assert txn is not None
        assert txn.provider_request_id == attempt["provider_request_id"]

    def test_idempotent_after_success(self, client, fake_jenga, db):
        headers, chama, member, conn = _scenario(client, fake_jenga)
        intent = _create_intent(client, headers, chama["id"], member["id"])
        first = _initiate(client, headers, chama["id"], intent["id"], conn["id"]).json()
        fake_jenga.query_results[first["provider_request_id"]] = StatusQueryResult(
            found=True,
            provider_request_id=first["provider_request_id"],
            normalized_status=_PTS.SUCCEEDED,
        )
        again = _initiate(client, headers, chama["id"], intent["id"], conn["id"])
        assert again.status_code == 200
        assert again.json()["status"] == "SUCCEEDED"
        assert again.json()["id"] == first["id"]
        row = db.scalar(
            select(PaymentIntent).where(PaymentIntent.id == uuid.UUID(intent["id"]))
        )
        assert row.status.value == "SUCCEEDED"

    def test_ambiguous_attempt_not_duplicated(self, client, fake_jenga, db):
        headers, chama, member, conn = _scenario(client, fake_jenga)
        intent = _create_intent(client, headers, chama["id"], member["id"])
        first = _initiate(client, headers, chama["id"], intent["id"], conn["id"]).json()
        again = _initiate(client, headers, chama["id"], intent["id"], conn["id"])
        assert again.status_code == 200
        assert again.json()["id"] == first["id"]
        attempts = db.scalars(
            select(PaymentAttempt).where(
                PaymentAttempt.payment_intent_id == uuid.UUID(intent["id"])
            )
        ).all()
        assert len(attempts) == 1

    def test_permanent_rejection_fails_intent(self, client, fake_jenga, db):
        headers, chama, member, conn = _scenario(client, fake_jenga)
        intent = _create_intent(client, headers, chama["id"], member["id"])
        ref = _attempt_reference(intent["id"], 1)
        fake_jenga.create_results[ref] = PaymentAttemptResult(
            accepted=False,
            retryable=False,
            error_code="AUTH_FAILED",
            error_message_safe="credentials rejected",
            normalized_status=_PTS.FAILED,
        )
        first = _initiate(client, headers, chama["id"], intent["id"], conn["id"])
        assert first.status_code == 200
        assert first.json()["status"] == "FAILED"
        assert first.json()["retryable"] is False
        again = _initiate(client, headers, chama["id"], intent["id"], conn["id"])
        assert again.status_code == 400
        assert "new payment intent" in again.json()["detail"]["message"].lower()
        row = db.scalar(
            select(PaymentIntent).where(PaymentIntent.id == uuid.UUID(intent["id"]))
        )
        assert row.status.value == "FAILED"

    def test_retryable_failure_creates_second_attempt(self, client, fake_jenga, db):
        headers, chama, member, conn = _scenario(client, fake_jenga)
        intent = _create_intent(client, headers, chama["id"], member["id"])
        ref = _attempt_reference(intent["id"], 1)
        fake_jenga.create_results[ref] = PaymentAttemptResult(
            accepted=False,
            retryable=True,
            error_code="PROVIDER_UNREACHABLE",
            error_message_safe="provider unreachable",
            normalized_status=_PTS.FAILED,
        )
        first = _initiate(client, headers, chama["id"], intent["id"], conn["id"]).json()
        assert first["status"] == "FAILED"
        assert first["retryable"] is True
        second = _initiate(client, headers, chama["id"], intent["id"], conn["id"])
        assert second.status_code == 200
        body = second.json()
        assert body["attempt_number"] == 2
        assert body["status"] == "INITIATED"
        attempts = db.scalars(
            select(PaymentAttempt).where(
                PaymentAttempt.payment_intent_id == uuid.UUID(intent["id"])
            )
        ).all()
        assert len(attempts) == 2

    def test_timeout_without_request_id_returns_same_attempt(self, client, fake_jenga, db):
        headers, chama, member, conn = _scenario(client, fake_jenga)
        intent = _create_intent(client, headers, chama["id"], member["id"])
        ref = _attempt_reference(intent["id"], 1)
        fake_jenga.create_exceptions[ref] = ProviderTimeoutError(
            "TIMEOUT", "Provider did not answer in time"
        )
        first = _initiate(client, headers, chama["id"], intent["id"], conn["id"]).json()
        assert first["status"] == "TIMEOUT"
        assert first["retryable"] is True
        assert first["provider_request_id"] is None
        second = _initiate(client, headers, chama["id"], intent["id"], conn["id"])
        assert second.status_code == 200
        assert second.json()["id"] == first["id"]
        assert second.json()["status"] == "TIMEOUT"

    def test_permanent_status_query_failure_fails_intent(self, client, fake_jenga, db):
        headers, chama, member, conn = _scenario(client, fake_jenga)
        intent = _create_intent(client, headers, chama["id"], member["id"])
        first = _initiate(client, headers, chama["id"], intent["id"], conn["id"]).json()
        assert first["status"] == "INITIATED"
        fake_jenga.query_results[first["provider_request_id"]] = StatusQueryResult(
            found=True,
            provider_request_id=first["provider_request_id"],
            normalized_status=_PTS.FAILED,
            error_code="AUTH_FAILED",
            error_message_safe="credentials rejected",
        )
        again = _initiate(client, headers, chama["id"], intent["id"], conn["id"])
        assert again.status_code == 400
        assert "new payment intent" in again.json()["detail"]["message"].lower()
        row = db.scalar(
            select(PaymentIntent).where(PaymentIntent.id == uuid.UUID(intent["id"]))
        )
        assert row.status.value == "FAILED"

    def test_retryable_status_query_failure_creates_second_attempt(
        self, client, fake_jenga, db
    ):
        headers, chama, member, conn = _scenario(client, fake_jenga)
        intent = _create_intent(client, headers, chama["id"], member["id"])
        first = _initiate(client, headers, chama["id"], intent["id"], conn["id"]).json()
        fake_jenga.query_results[first["provider_request_id"]] = StatusQueryResult(
            found=True,
            provider_request_id=first["provider_request_id"],
            normalized_status=_PTS.FAILED,
            error_code="PROVIDER_UNREACHABLE",
            error_message_safe="provider unreachable",
        )
        second = _initiate(client, headers, chama["id"], intent["id"], conn["id"])
        assert second.status_code == 200
        body = second.json()
        assert body["attempt_number"] == 2
        assert body["status"] == "INITIATED"
        attempts = db.scalars(
            select(PaymentAttempt).where(
                PaymentAttempt.payment_intent_id == uuid.UUID(intent["id"])
            )
        ).all()
        assert len(attempts) == 2

    def test_failed_intent_cannot_be_restarted(self, client, fake_jenga):
        headers, chama, member, conn = _scenario(client, fake_jenga)
        intent = _create_intent(client, headers, chama["id"], member["id"])
        ref = _attempt_reference(intent["id"], 1)
        fake_jenga.create_results[ref] = PaymentAttemptResult(
            accepted=False,
            retryable=False,
            error_code="AUTH_FAILED",
            error_message_safe="rejected",
            normalized_status=_PTS.FAILED,
        )
        _initiate(client, headers, chama["id"], intent["id"], conn["id"])
        again = _initiate(client, headers, chama["id"], intent["id"], conn["id"])
        assert again.status_code == 400
        assert "new payment intent" in again.json()["detail"]["message"].lower()

    def test_initiate_requires_active_connection(self, client, fake_jenga):
        headers, chama, member, conn = _scenario(client, fake_jenga)
        intent = _create_intent(client, headers, chama["id"], member["id"])
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payment-connections/{conn['id']}/disable",
            headers=headers,
        )
        assert r.status_code == 200
        resp = _initiate(client, headers, chama["id"], intent["id"], conn["id"])
        assert resp.status_code == 400
        assert "not active" in resp.json()["detail"]["message"].lower()


class TestIntentRead:
    def test_cross_chama_intent_isolation(self, client, fake_jenga):
        headers, chama, member, conn = _scenario(client, fake_jenga)
        intent = _create_intent(client, headers, chama["id"], member["id"])
        outsider = register_and_login(client, "outsider@e.com")
        r = client.get(
            f"/api/v1/chamas/{chama['id']}/payment-intents/{intent['id']}",
            headers=outsider,
        )
        assert r.status_code == 403