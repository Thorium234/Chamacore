"""STK/status-query settlement of payment intents linked to contributions (ADR-019).

When a payment intent carrying a ``contribution_id`` reaches SUCCEEDED via a
provider callback or a status query, the linked PENDING contribution is
confirmed and posted to the ledger as the system user.
"""

import uuid

import pytest
from sqlalchemy import select

from app.models.enums import PaymentEnvironment, PaymentProviderCode
from app.models.ledger_transaction import LedgerTransaction
from app.services.ledger import CONTRIBUTION_SOURCE_TYPE, REVERSAL_SOURCE_TYPE
from tests.conftest import add_membership, create_chama, register_and_login
from tests.fake_provider import (
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
    return headers, chama, member, conn


def _record_contribution(client, headers, chama_id, membership_id, *, amount="50.00", period="2026-09"):
    r = client.post(
        f"/api/v1/chamas/{chama_id}/contributions",
        headers=headers,
        json={"membership_id": membership_id, "amount": amount, "period": period},
    )
    assert r.status_code == 201, r.json()
    return r.json()


def _create_linked_intent(client, headers, chama_id, member_id, contribution_id, *, key="settle-1", amount="50.00"):
    r = client.post(
        f"/api/v1/chamas/{chama_id}/payment-intents",
        headers=headers,
        json={
            "membership_id": member_id,
            "amount": amount,
            "currency": "KES",
            "purpose": "monthly contribution",
            "idempotency_key": key,
            "contribution_id": contribution_id,
        },
    )
    assert r.status_code == 201, r.json()
    return r.json()


def _postings(db):
    return list(
        db.scalars(
            select(LedgerTransaction).where(
                LedgerTransaction.source_type == CONTRIBUTION_SOURCE_TYPE
            )
        )
    )


def _contribution_status(db, contribution_id):
    from app.models.contribution import Contribution

    return db.get(Contribution, uuid.UUID(contribution_id)).status


class TestLinkedIntentCreate:
    def test_link_pending_contribution(self, client, fake_jenga):
        headers, chama, member, conn = _scenario(client, fake_jenga)
        contribution = _record_contribution(client, headers, chama["id"], member["id"])
        intent = _create_linked_intent(
            client, headers, chama["id"], member["id"], contribution["id"]
        )
        assert intent["contribution_id"] == contribution["id"]

    def test_amount_mismatch_rejected(self, client, fake_jenga):
        headers, chama, member, conn = _scenario(client, fake_jenga)
        contribution = _record_contribution(client, headers, chama["id"], member["id"])
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payment-intents",
            headers=headers,
            json={
                "membership_id": member["id"],
                "amount": "999.00",
                "currency": "KES",
                "purpose": "monthly contribution",
                "idempotency_key": "settle-mismatch",
                "contribution_id": contribution["id"],
            },
        )
        assert r.status_code == 400
        assert "match the linked contribution" in r.json()["detail"]["message"]

    def test_link_to_other_membership_rejected(self, client, fake_jenga, db):
        headers, chama, member, conn = _scenario(client, fake_jenga)
        other = add_membership(
            client, headers, chama["id"], phone="+254700000101", govt="GID-101"
        )
        contribution = _record_contribution(client, headers, chama["id"], other["id"])
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payment-intents",
            headers=headers,
            json={
                "membership_id": member["id"],
                "amount": "50.00",
                "currency": "KES",
                "purpose": "monthly contribution",
                "idempotency_key": "settle-other-member",
                "contribution_id": contribution["id"],
            },
        )
        assert r.status_code == 400
        assert "linked contribution" in r.json()["detail"]["message"]

    def test_link_confirmed_contribution_rejected(self, client, fake_jenga):
        headers, chama, member, conn = _scenario(client, fake_jenga)
        contribution = _record_contribution(client, headers, chama["id"], member["id"])
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions/{contribution['id']}/confirm",
            headers=headers,
        )
        assert r.status_code == 200
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payment-intents",
            headers=headers,
            json={
                "membership_id": member["id"],
                "amount": "50.00",
                "currency": "KES",
                "purpose": "monthly contribution",
                "idempotency_key": "settle-confirmed",
                "contribution_id": contribution["id"],
            },
        )
        assert r.status_code == 400
        assert "PENDING" in r.json()["detail"]["message"]


class TestStatusQuerySettlement:
    def test_success_confirm_confirms_and_posts_ledger(self, client, fake_jenga, db):
        headers, chama, member, conn = _scenario(client, fake_jenga)
        contribution = _record_contribution(client, headers, chama["id"], member["id"])
        intent = _create_linked_intent(
            client, headers, chama["id"], member["id"], contribution["id"]
        )
        first = client.post(
            f"/api/v1/chamas/{chama['id']}/payment-intents/{intent['id']}/initiate",
            headers=headers,
            json={"connection_id": conn["id"]},
        ).json()
        fake_jenga.query_results[first["provider_request_id"]] = StatusQueryResult(
            found=True,
            provider_request_id=first["provider_request_id"],
            normalized_status=_PTS.SUCCEEDED,
        )
        again = client.post(
            f"/api/v1/chamas/{chama['id']}/payment-intents/{intent['id']}/initiate",
            headers=headers,
            json={"connection_id": conn["id"]},
        )
        assert again.status_code == 200
        assert again.json()["status"] == "SUCCEEDED"
        assert _contribution_status(db, contribution["id"]).value == "CONFIRMED"
        assert len(_postings(db)) == 1
        posting = _postings(db)[0]
        assert posting.source_id == uuid.UUID(contribution["id"])
        assert sum(e.debit for e in posting.entries) == 50
        assert sum(e.credit for e in posting.entries) == 50

    def test_settlement_is_idempotent(self, client, fake_jenga, db):
        headers, chama, member, conn = _scenario(client, fake_jenga)
        contribution = _record_contribution(client, headers, chama["id"], member["id"])
        intent = _create_linked_intent(
            client, headers, chama["id"], member["id"], contribution["id"]
        )
        first = client.post(
            f"/api/v1/chamas/{chama['id']}/payment-intents/{intent['id']}/initiate",
            headers=headers,
            json={"connection_id": conn["id"]},
        ).json()
        fake_jenga.query_results[first["provider_request_id"]] = StatusQueryResult(
            found=True,
            provider_request_id=first["provider_request_id"],
            normalized_status=_PTS.SUCCEEDED,
        )
        initiate = lambda: client.post(  # noqa: E731
            f"/api/v1/chamas/{chama['id']}/payment-intents/{intent['id']}/initiate",
            headers=headers,
            json={"connection_id": conn["id"]},
        )
        assert initiate().json()["status"] == "SUCCEEDED"
        assert initiate().json()["status"] == "SUCCEEDED"
        assert len(_postings(db)) == 1

    def test_failure_leaves_contribution_pending(self, client, fake_jenga, db):
        headers, chama, member, conn = _scenario(client, fake_jenga)
        contribution = _record_contribution(client, headers, chama["id"], member["id"])
        intent = _create_linked_intent(
            client, headers, chama["id"], member["id"], contribution["id"]
        )
        first = client.post(
            f"/api/v1/chamas/{chama['id']}/payment-intents/{intent['id']}/initiate",
            headers=headers,
            json={"connection_id": conn["id"]},
        ).json()
        fake_jenga.query_results[first["provider_request_id"]] = StatusQueryResult(
            found=True,
            provider_request_id=first["provider_request_id"],
            normalized_status=_PTS.FAILED,
            error_code="AUTH_FAILED",
            error_message_safe="rejected",
        )
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payment-intents/{intent['id']}/initiate",
            headers=headers,
            json={"connection_id": conn["id"]},
        )
        assert r.status_code == 400
        assert _contribution_status(db, contribution["id"]).value == "PENDING"
        assert _postings(db) == []

    def test_reversed_after_settlement_posts_compensating_reversal(self, client, fake_jenga, db):
        headers, chama, member, conn = _scenario(client, fake_jenga)
        contribution = _record_contribution(client, headers, chama["id"], member["id"])
        intent = _create_linked_intent(
            client, headers, chama["id"], member["id"], contribution["id"]
        )
        first = client.post(
            f"/api/v1/chamas/{chama['id']}/payment-intents/{intent['id']}/initiate",
            headers=headers,
            json={"connection_id": conn["id"]},
        ).json()
        fake_jenga.query_results[first["provider_request_id"]] = StatusQueryResult(
            found=True,
            provider_request_id=first["provider_request_id"],
            normalized_status=_PTS.SUCCEEDED,
        )
        client.post(
            f"/api/v1/chamas/{chama['id']}/payment-intents/{intent['id']}/initiate",
            headers=headers,
            json={"connection_id": conn["id"]},
        )
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions/{contribution['id']}/reverse",
            headers=headers,
            json={"note": "system settled in error"},
        )
        assert r.status_code == 200
        txns = db.scalars(select(LedgerTransaction).order_by(LedgerTransaction.created_at)).all()
        assert len(txns) == 2
        posting, reversal = txns
        assert posting.source_type == CONTRIBUTION_SOURCE_TYPE
        assert reversal.source_type == REVERSAL_SOURCE_TYPE
        assert reversal.reverses_transaction_id == posting.id


class TestCallbackSettlement:
    def _callback_url(self, conn: dict) -> str:
        from app.core.callback_utils import connection_callback_token

        token = connection_callback_token(
            connection_id=uuid.UUID(conn["id"]),
            provider_code=PaymentProviderCode(conn["provider_code"]),
            environment=PaymentEnvironment(conn["environment"]),
        )
        return (
            f"/api/v1/payments/webhooks/{conn['provider_code']}/{conn['environment']}"
            f"?connection_id={conn['id']}&token={token}"
        )

    def test_callback_success_settles_linked_contribution(self, client, fake_jenga, db):
        headers, chama, member, conn = _scenario(client, fake_jenga)
        contribution = _record_contribution(client, headers, chama["id"], member["id"])
        intent = _create_linked_intent(
            client, headers, chama["id"], member["id"], contribution["id"]
        )
        first = client.post(
            f"/api/v1/chamas/{chama['id']}/payment-intents/{intent['id']}/initiate",
            headers=headers,
            json={"connection_id": conn["id"]},
        ).json()
        payload = {
            "provider_event_id": "EVT-SETTLE-1",
            "provider_request_id": first["provider_request_id"],
            "provider_transaction_id": "TXN-SETTLE-1",
            "amount": "50.00",
            "currency": "KES",
            "normalized_status": "SUCCEEDED",
        }
        r = client.post(
            self._callback_url(conn),
            content=payload if isinstance(payload, bytes) else str(payload).replace("'", '"').encode(),
            headers={"content-type": "application/json"},
        )
        assert r.status_code in (200, 202), r.text
        assert _contribution_status(db, contribution["id"]).value == "CONFIRMED"
        assert len(_postings(db)) == 1
        assert _postings(db)[0].posted_by_user_id == uuid.UUID(
            "6f1c3a5e-0000-4000-8000-0000000000a1"
        )

    def test_callback_for_unlinked_intent_no_settlement(self, client, fake_jenga, db):
        headers, chama, member, conn = _scenario(client, fake_jenga)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payment-intents",
            headers=headers,
            json={
                "membership_id": member["id"],
                "amount": "50.00",
                "currency": "KES",
                "purpose": "monthly contribution",
                "idempotency_key": "unlinked-1",
            },
        )
        intent = r.json()
        first = client.post(
            f"/api/v1/chamas/{chama['id']}/payment-intents/{intent['id']}/initiate",
            headers=headers,
            json={"connection_id": conn["id"]},
        ).json()
        payload = {
            "provider_event_id": "EVT-SETTLE-2",
            "provider_request_id": first["provider_request_id"],
            "provider_transaction_id": "TXN-SETTLE-2",
            "amount": "50.00",
            "currency": "KES",
            "normalized_status": "SUCCEEDED",
        }
        r = client.post(
            self._callback_url(conn),
            content=str(payload).replace("'", '"').encode(),
            headers={"content-type": "application/json"},
        )
        assert r.status_code in (200, 202), r.text
        assert _postings(db) == []