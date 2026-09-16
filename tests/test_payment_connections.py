"""Payment connection lifecycle API tests (ADR-017)."""

import uuid

import pytest
from sqlalchemy import select

from app.models.enums import PaymentEnvironment, PaymentProviderCode
from tests.conftest import create_chama, register_and_login
from tests.fake_provider import setup_fake_adapter, restore_fake_adapter

JENGA = PaymentProviderCode.JENGA.value
SANDBOX = PaymentEnvironment.SANDBOX.value


def _jenga_credentials(**overrides) -> dict:
    base = {
        "api_key": "ak_123",
        "merchant_code": "M1001",
        "consumer_secret": "cs_secret_value",
    }
    base.update(overrides)
    return base


@pytest.fixture()
def fake_jenga():
    fake = setup_fake_adapter(PaymentProviderCode.JENGA, PaymentEnvironment.SANDBOX)
    try:
        yield fake
    finally:
        restore_fake_adapter(PaymentProviderCode.JENGA, PaymentEnvironment.SANDBOX)


def _chair(client):
    return register_and_login(client, "chair@e.com")


def _member(client):
    return register_and_login(client, "member@e.com")


def _create_pending_connection(client, headers, chama_id: str) -> dict:
    r = client.post(
        f"/api/v1/chamas/{chama_id}/payment-connections",
        headers=headers,
        json={
            "provider_code": JENGA,
            "environment": SANDBOX,
            "credentials": _jenga_credentials(),
        },
    )
    assert r.status_code == 201, r.json()
    return r.json()


def _validate(client, headers, chama_id: str, connection_id: str) -> dict:
    r = client.post(
        f"/api/v1/chamas/{chama_id}/payment-connections/{connection_id}/validate",
        headers=headers,
    )
    assert r.status_code == 200, r.json()
    return r.json()


class TestCreateConnection:
    def test_chairperson_creates_connection(self, client, fake_jenga):
        headers = _chair(client)
        chama = create_chama(client, headers)
        conn = _create_pending_connection(client, headers, chama["id"])
        assert conn["status"] == "PENDING_VALIDATION"
        assert conn["provider_code"] == JENGA
        assert conn["environment"] == SANDBOX
        assert conn["credential_version"] == 1
        assert conn["masked_account_identifier"]

    def test_credentials_never_exposed(self, client, fake_jenga):
        headers = _chair(client)
        chama = create_chama(client, headers)
        conn = _create_pending_connection(client, headers, chama["id"])
        body = client.get(
            f"/api/v1/chamas/{chama['id']}/payment-connections/{conn['id']}",
            headers=headers,
        ).json()
        for key in ("credentials", "encrypted_credentials", "api_key", "consumer_secret", "merchant_code"):
            assert key not in body
        assert len(conn) == len(body)

    def test_credentials_sealed_in_database(self, client, fake_jenga, db):
        headers = _chair(client)
        chama = create_chama(client, headers)
        _create_pending_connection(client, headers, chama["id"])
        from app.models.payment_connection import PaymentConnection

        record = db.scalar(select(PaymentConnection))
        assert record is not None
        for secret in ("ak_123", "cs_secret_value", "M1001"):
            assert secret not in record.encrypted_credentials

    def test_non_chairperson_cannot_create(self, client, fake_jenga):
        headers = _chair(client)
        chama = create_chama(client, headers)
        headers_member = _member(client)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payment-connections",
            headers=headers_member,
            json={
                "provider_code": JENGA,
                "environment": SANDBOX,
                "credentials": _jenga_credentials(),
            },
        )
        assert r.status_code in (403, 400)
        assert r.json()["detail"]["code"] == "PERMISSION_DENIED"

    def test_duplicate_provider_environment_conflicts(self, client, fake_jenga):
        headers = _chair(client)
        chama = create_chama(client, headers)
        _create_pending_connection(client, headers, chama["id"])
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payment-connections",
            headers=headers,
            json={
                "provider_code": JENGA,
                "environment": SANDBOX,
                "credentials": _jenga_credentials(),
            },
        )
        assert r.status_code == 409

    def test_cross_chama_isolation(self, client, fake_jenga):
        headers_a = _chair(client)
        chama_a = create_chama(client, headers_a, name="Chama A")
        conn = _create_pending_connection(client, headers_a, chama_a["id"])
        headers_b = register_and_login(client, "other@e.com")
        chama_b = create_chama(
            client, headers_b, name="Chama B",
            phone="+254700000777", govt="GID-777",
        )
        r = client.get(
            f"/api/v1/chamas/{chama_a['id']}/payment-connections/{conn['id']}",
            headers=headers_b,
        )
        assert r.status_code == 403

    def test_unknown_chama_not_found(self, client, fake_jenga):
        headers = _chair(client)
        r = client.post(
            f"/api/v1/chamas/{uuid.uuid4()}/payment-connections",
            headers=headers,
            json={
                "provider_code": JENGA,
                "environment": SANDBOX,
                "credentials": _jenga_credentials(),
            },
        )
        assert r.status_code == 404


class TestValidate:
    def test_validation_activates_connection(self, client, fake_jenga):
        headers = _chair(client)
        chama = create_chama(client, headers)
        conn = _create_pending_connection(client, headers, chama["id"])
        validated = _validate(client, headers, chama["id"], conn["id"])
        assert validated["status"] == "ACTIVE"
        assert validated["last_validated_at"] is not None
        assert validated["last_validation_error_code"] is None

    def test_validate_active_connection_rejected(self, client, fake_jenga):
        headers = _chair(client)
        chama = create_chama(client, headers)
        conn = _create_pending_connection(client, headers, chama["id"])
        _validate(client, headers, chama["id"], conn["id"])
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payment-connections/{conn['id']}/validate",
            headers=headers,
        )
        assert r.status_code == 400
        assert "already active" in r.json()["detail"]["message"].lower()

    def test_failed_validation_becomes_invalid(self, client, fake_jenga):
        fake_jenga.valid_credentials = False
        headers = _chair(client)
        chama = create_chama(client, headers)
        conn = _create_pending_connection(client, headers, chama["id"])
        validated = _validate(client, headers, chama["id"], conn["id"])
        assert validated["status"] == "INVALID"
        assert validated["last_validation_error_code"] == "AUTH_FAILED"

    def test_member_cannot_validate(self, client, fake_jenga):
        headers = _chair(client)
        chama = create_chama(client, headers)
        conn = _create_pending_connection(client, headers, chama["id"])
        headers_member = _member(client)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payment-connections/{conn['id']}/validate",
            headers=headers_member,
        )
        assert r.status_code == 403

    def test_disabled_connection_stays_disabled_after_test(self, client, fake_jenga):
        headers = _chair(client)
        chama = create_chama(client, headers)
        conn = _create_pending_connection(client, headers, chama["id"])
        client.post(
            f"/api/v1/chamas/{chama['id']}/payment-connections/{conn['id']}/disable",
            headers=headers,
        )
        after = _validate(client, headers, chama["id"], conn["id"])
        assert after["status"] == "DISABLED"

    def test_disabled_connection_stays_disabled_on_failure(self, client, fake_jenga):
        fake_jenga.valid_credentials = False
        headers = _chair(client)
        chama = create_chama(client, headers)
        conn = _create_pending_connection(client, headers, chama["id"])
        client.post(
            f"/api/v1/chamas/{chama['id']}/payment-connections/{conn['id']}/disable",
            headers=headers,
        )
        after = _validate(client, headers, chama["id"], conn["id"])
        assert after["status"] == "DISABLED"
        assert after["last_validation_error_code"] == "AUTH_FAILED"

    def test_validate_rate_limit(self, client, fake_jenga):
        headers = _chair(client)
        chama = create_chama(client, headers)
        conn = _create_pending_connection(client, headers, chama["id"])
        client.post(
            f"/api/v1/chamas/{chama['id']}/payment-connections/{conn['id']}/disable",
            headers=headers,
        )
        for _ in range(5):
            r = client.post(
                f"/api/v1/chamas/{chama['id']}/payment-connections/{conn['id']}/validate",
                headers=headers,
            )
            assert r.status_code == 200
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payment-connections/{conn['id']}/validate",
            headers=headers,
        )
        assert r.status_code == 429


class TestReplace:
    def test_replace_bumps_version_and_requires_validation(self, client, fake_jenga):
        headers = _chair(client)
        chama = create_chama(client, headers)
        conn = _create_pending_connection(client, headers, chama["id"])
        _validate(client, headers, chama["id"], conn["id"])
        r = client.patch(
            f"/api/v1/chamas/{chama['id']}/payment-connections/{conn['id']}",
            headers=headers,
            json={"credentials": _jenga_credentials(api_key="ak_456")},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "PENDING_VALIDATION"
        assert body["credential_version"] == 2
        validated = _validate(client, headers, chama["id"], conn["id"])
        assert validated["status"] == "ACTIVE"
        assert validated["credential_version"] == 2

    def test_replace_new_creds_sealed(self, client, fake_jenga, db):
        headers = _chair(client)
        chama = create_chama(client, headers)
        conn = _create_pending_connection(client, headers, chama["id"])
        r = client.patch(
            f"/api/v1/chamas/{chama['id']}/payment-connections/{conn['id']}",
            headers=headers,
            json={"credentials": _jenga_credentials(consumer_secret="new_top_secret")},
        )
        assert r.status_code == 200
        from app.models.payment_connection import PaymentConnection

        record = db.scalar(select(PaymentConnection))
        assert "new_top_secret" not in record.encrypted_credentials


class TestDisable:
    def test_disable_blocks_reenable(self, client, fake_jenga):
        headers = _chair(client)
        chama = create_chama(client, headers)
        conn = _create_pending_connection(client, headers, chama["id"])
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payment-connections/{conn['id']}/disable",
            headers=headers,
        )
        assert r.json()["status"] == "DISABLED"
        r = client.get(
            f"/api/v1/chamas/{chama['id']}/payment-connections/{conn['id']}",
            headers=headers,
        )
        assert r.json()["status"] == "DISABLED"

    def test_disable_is_idempotent(self, client, fake_jenga):
        headers = _chair(client)
        chama = create_chama(client, headers)
        conn = _create_pending_connection(client, headers, chama["id"])
        client.post(
            f"/api/v1/chamas/{chama['id']}/payment-connections/{conn['id']}/disable",
            headers=headers,
        )
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payment-connections/{conn['id']}/disable",
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "DISABLED"


class TestDelete:
    def test_delete_without_history(self, client, fake_jenga):
        headers = _chair(client)
        chama = create_chama(client, headers)
        conn = _create_pending_connection(client, headers, chama["id"])
        r = client.delete(
            f"/api/v1/chamas/{chama['id']}/payment-connections/{conn['id']}",
            headers=headers,
        )
        assert r.status_code == 204
        r = client.get(
            f"/api/v1/chamas/{chama['id']}/payment-connections/{conn['id']}",
            headers=headers,
        )
        assert r.status_code == 400

    def test_delete_with_event_history_conflicts(self, client, fake_jenga, db):
        headers = _chair(client)
        chama = create_chama(client, headers)
        conn = _create_pending_connection(client, headers, chama["id"])
        from datetime import datetime, timezone

        from app.models.payment_event import PaymentEvent

        db.add(
            PaymentEvent(
                id=uuid.uuid4(),
                connection_id=uuid.UUID(conn["id"]),
                provider_code=PaymentProviderCode.JENGA,
                environment=PaymentEnvironment.SANDBOX,
                provider_event_id="EVT-DELETE",
                payload_hash="0" * 64,
                raw_payload="{}",
                status="RECEIVED",
                received_at=datetime.now(timezone.utc),
                last_transition_source="PROVIDER_CALLBACK",
            )
        )
        db.commit()
        r = client.delete(
            f"/api/v1/chamas/{chama['id']}/payment-connections/{conn['id']}",
            headers=headers,
        )
        assert r.status_code == 409
        assert "payment history" in r.json()["detail"]["message"].lower()

    def test_non_chairperson_cannot_delete(self, client, fake_jenga):
        headers = _chair(client)
        chama = create_chama(client, headers)
        conn = _create_pending_connection(client, headers, chama["id"])
        headers_member = _member(client)
        r = client.delete(
            f"/api/v1/chamas/{chama['id']}/payment-connections/{conn['id']}",
            headers=headers_member,
        )
        assert r.status_code == 403


class TestList:
    def test_any_member_can_list(self, client, fake_jenga):
        headers = _chair(client)
        chama = create_chama(client, headers)
        _create_pending_connection(client, headers, chama["id"])
        headers_member = _member(client)
        member_chama = create_chama(
            client, headers_member, name="Member Chama",
            phone="+254700000778", govt="GID-778",
        )
        members = client.get(
            f"/api/v1/chamas/{member_chama['id']}/memberships",
            headers=headers_member,
        ).json()
        member_id = members[0]["member_id"]
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/memberships",
            headers=headers,
            json={"member_id": member_id},
        )
        assert r.status_code == 201, r.json()
        r = client.get(
            f"/api/v1/chamas/{chama['id']}/payment-connections",
            headers=headers_member,
        )
        assert r.status_code == 200
        assert len(r.json()) == 1