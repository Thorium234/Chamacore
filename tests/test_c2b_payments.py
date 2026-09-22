"""C2B (manual Paybill) validation + confirmation tests (ADR-016, OQ-021, ADR-019).

OQ-021 rules under test:
- validation ACCEPTS (ResultCode 0) only when the connection is ACTIVE, the
  payload parses, the short code matches, and BillRefNumber is an ACTIVE
  membership number in the Chama; otherwise it REJECTS (ResultCode 1).
- confirmation is stored idempotently (deduplicated by TransID), creates or
  reuses a CONFIRMED contribution for the current YYYY-MM period and posts it
  through the OQ-013 ledger path; disagreements surface as DISAGREEMENT.
"""

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
)
from app.models.membership import Membership
from app.models.payment_event import PaymentEvent
from app.providers.errors import ProviderIntegrationError
from app.services.ledger import CONTRIBUTION_SOURCE_TYPE
from tests.conftest import register_and_login
from tests.fake_provider import restore_fake_adapter, setup_fake_adapter

DARAJA = PaymentProviderCode.DARAJA.value
SANDBOX = PaymentEnvironment.SANDBOX.value


def _c2b_payload(*, trans_id="RKTQDM7W6w", amount="100", short_code="600598", bill_ref="1"):
    return {
        "TransactionType": "Pay Bill",
        "TransID": trans_id,
        "TransTime": "20191122063805",
        "TransAmount": amount,
        "BusinessShortCode": short_code,
        "BillRefNumber": bill_ref,
        "InvoiceNumber": "",
        "OrgAccountBalance": "142.00",
        "ThirdPartyTransID": "",
        "MSISDN": "254708374149",
        "FirstName": "John",
        "MiddleName": "",
        "LastName": "Doe",
    }


def _setup(client):
    headers = register_and_login(client, "c2b@e.com")
    r = client.post(
        "/api/v1/chamas",
        headers=headers,
        json={
            "name": "C2B Chama",
            "registration_fee_amount": "100.00",
            "member": {
                "first_name": "Alice",
                "last_name": "Wanjiku",
                "phone_number": "+254700000201",
                "government_id": "GID-201",
            },
        },
    )
    assert r.status_code == 201
    chama = r.json()
    r = client.post(
        f"/api/v1/chamas/{chama['id']}/payment-connections",
        headers=headers,
        json={
            "provider_code": DARAJA,
            "environment": SANDBOX,
            "credentials": {
                "consumer_key": "ck-c2b",
                "consumer_secret": "cs-c2b",
                "short_code": "600598",
                "passkey": "pk-c2b",
            },
        },
    )
    assert r.status_code == 201
    conn = r.json()
    token = connection_callback_token(
        connection_id=uuid.UUID(conn["id"]),
        provider_code=PaymentProviderCode.DARAJA,
        environment=PaymentEnvironment.SANDBOX,
    )
    urls = {
        "validate": f"/api/v1/payments/c2b/validate/{conn['id']}?token={token}",
        "confirm": f"/api/v1/payments/c2b/confirm/{conn['id']}?token={token}",
    }
    return headers, chama, conn, urls


def _activate(client, headers, chama, conn):
    """Activate a connection through the validate endpoint using the fake adapter."""
    fake = setup_fake_adapter(PaymentProviderCode.DARAJA, PaymentEnvironment.SANDBOX)
    try:
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payment-connections/{conn['id']}/validate",
            headers=headers,
        )
        assert r.status_code == 200, f"activate failed: {r.json()}"
    finally:
        restore_fake_adapter(PaymentProviderCode.DARAJA, PaymentEnvironment.SANDBOX)


def _post(client, url, payload):
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return client.post(url, content=body, headers={"content-type": "application/json"})


def _events(db) -> list[PaymentEvent]:
    return list(db.scalars(select(PaymentEvent).order_by(PaymentEvent.received_at)))


def _ledger_count(db) -> int:
    from app.models.ledger_transaction import LedgerTransaction

    return len(list(db.scalars(select(LedgerTransaction))))


def _contribution_postings(db):
    from app.models.ledger_transaction import LedgerTransaction

    return list(
        db.scalars(
            select(LedgerTransaction).where(
                LedgerTransaction.source_type == CONTRIBUTION_SOURCE_TYPE
            )
        )
    )


class TestC2BValidation:
    def test_validation_accepts_active_member(self, client, db):
        headers, chama, conn, urls = _setup(client)
        _activate(client, headers, chama, conn)
        r = _post(client, urls["validate"], _c2b_payload(bill_ref="1"))
        assert r.status_code == 200
        assert r.json()["ResultCode"] == 0
        events = _events(db)
        assert len(events) == 1
        assert events[0].status == PaymentEventStatus.PROCESSED
        assert events[0].provider_event_id == "C2B_VALIDATION:RKTQDM7W6w"
        assert _ledger_count(db) == 0

    def test_validation_rejects_unknown_membership_number(self, client, db):
        headers, chama, conn, urls = _setup(client)
        _activate(client, headers, chama, conn)
        r = _post(client, urls["validate"], _c2b_payload(bill_ref="999999"))
        assert r.status_code == 200
        assert r.json()["ResultCode"] == 1
        events = _events(db)
        assert events[0].status == PaymentEventStatus.REJECTED
        assert _ledger_count(db) == 0

    def test_validation_rejects_non_numeric_reference(self, client, db):
        headers, chama, conn, urls = _setup(client)
        _activate(client, headers, chama, conn)
        r = _post(client, urls["validate"], _c2b_payload(bill_ref="abc"))
        assert r.status_code == 200
        assert r.json()["ResultCode"] == 1
        assert "not a membership number" in r.json()["ResultDesc"]

    def test_validation_rejects_inactive_connection(self, client, db):
        _, _, _, urls = _setup(client)
        r = _post(client, urls["validate"], _c2b_payload(bill_ref="1"))
        assert r.status_code == 200
        assert r.json()["ResultCode"] == 1
        assert "not active" in r.json()["ResultDesc"]
        events = _events(db)
        assert events[0].status == PaymentEventStatus.REJECTED

    def test_validation_rejects_at_shortcode_mismatch(self, client, db):
        headers, chama, conn, urls = _setup(client)
        _activate(client, headers, chama, conn)
        r = _post(client, urls["validate"], _c2b_payload(bill_ref="1", short_code="999999"))
        assert r.status_code == 200
        assert r.json()["ResultCode"] == 1
        assert "short code" in r.json()["ResultDesc"]

    def test_validation_invalid_token_rejects_without_event(self, client, db):
        _, _, conn, _ = _setup(client)
        url = f"/api/v1/payments/c2b/validate/{conn['id']}?token=wrong"
        r = _post(client, url, _c2b_payload(bill_ref="1"))
        assert r.status_code == 200
        assert r.json()["ResultCode"] == 1
        assert _events(db) == []

    def test_validation_unknown_connection_rejects(self, client):
        _, _, _, _ = _setup(client)
        bogus = str(uuid.uuid4())
        r = _post(
            client,
            f"/api/v1/payments/c2b/validate/{bogus}?token=wrong",
            _c2b_payload(bill_ref="1"),
        )
        assert r.status_code == 200
        assert r.json()["ResultCode"] == 1


class TestC2BConfirmation:
    def test_confirmation_settles_and_posts_ledger(self, client, db):
        headers, chama, conn, urls = _setup(client)
        _activate(client, headers, chama, conn)
        r = _post(client, urls["confirm"], _c2b_payload(bill_ref="1", amount="100"))
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["event_status"] == "PROCESSED"
        events = _events(db)
        assert len(events) == 1
        assert events[0].provider_event_id == "C2B_CONFIRMATION:RKTQDM7W6w"
        postings = _contribution_postings(db)
        assert len(postings) == 1
        assert sum(e.debit for t in postings for e in t.entries) == 100
        assert sum(e.credit for t in postings for e in t.entries) == 100

    def test_confirmation_duplicate_delivery_is_deduplicated(self, client, db):
        headers, chama, conn, urls = _setup(client)
        _activate(client, headers, chama, conn)
        first = _post(client, urls["confirm"], _c2b_payload(bill_ref="1")).json()
        second = _post(client, urls["confirm"], _c2b_payload(bill_ref="1")).json()
        assert first["event_status"] == "PROCESSED"
        assert second["event_status"] == "DEDUPLICATED"
        assert len(_events(db)) == 1
        assert len(_contribution_postings(db)) == 1

    def test_confirmation_same_trans_id_different_body_disagrees(self, client, db):
        headers, chama, conn, urls = _setup(client)
        _activate(client, headers, chama, conn)
        _post(client, urls["confirm"], _c2b_payload(bill_ref="1"))
        r = _post(client, urls["confirm"], _c2b_payload(bill_ref="1", amount="999"))
        assert r.json()["event_status"] == "DISAGREEMENT"
        assert len(_events(db)) == 1

    def test_confirmation_shortcode_mismatch_is_unprocessable(self, client, db):
        headers, chama, conn, urls = _setup(client)
        _activate(client, headers, chama, conn)
        r = _post(client, urls["confirm"], _c2b_payload(bill_ref="1", short_code="999999"))
        assert r.status_code == 200
        assert r.json()["event_status"] == "UNPROCESSABLE"
        assert _ledger_count(db) == 0

    def test_confirmation_unknown_member_disagrees(self, client, db):
        headers, chama, conn, urls = _setup(client)
        _activate(client, headers, chama, conn)
        r = _post(client, urls["confirm"], _c2b_payload(bill_ref="999999"))
        assert r.status_code == 200
        assert r.json()["event_status"] == "DISAGREEMENT"
        assert _ledger_count(db) == 0

    def test_confirmation_inactive_connection_is_unprocessable(self, client, db):
        _, _, _, urls = _setup(client)
        r = _post(client, urls["confirm"], _c2b_payload(bill_ref="1"))
        assert r.status_code == 200
        assert r.json()["event_status"] == "UNPROCESSABLE"
        assert _ledger_count(db) == 0

    def test_confirmation_pending_contrib_amount_mismatch_disagrees(self, client, db):
        from datetime import datetime, timezone

        from app.repositories.contribution import ContributionRepository

        headers, chama, conn, urls = _setup(client)
        _activate(client, headers, chama, conn)
        membership = db.scalars(
            select(Membership).where(Membership.chama_id == uuid.UUID(chama["id"]))
        ).one()
        period = datetime.now(timezone.utc).strftime("%Y-%m")
        ContributionRepository(db).create(
            membership_id=membership.id,
            amount=Decimal("50.00"),
            period=period,
            recorded_by_user_id=uuid.UUID("6f1c3a5e-0000-4000-8000-0000000000a1"),
            note="existing pending",
        )
        db.commit()
        r = _post(client, urls["confirm"], _c2b_payload(bill_ref="1", amount="100"))
        assert r.json()["event_status"] == "DISAGREEMENT"

    def test_confirmation_invalid_token_is_rejected(self, client, db):
        _, _, conn, _ = _setup(client)
        url = f"/api/v1/payments/c2b/confirm/{conn['id']}?token=wrong"
        r = _post(client, url, _c2b_payload(bill_ref="1"))
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "WEBHOOK_REJECTED"
        assert _events(db) == []

    def test_confirmation_malformed_payload_is_stored_unprocessable(self, client, db):
        _, _, _, urls = _setup(client)
        r = _post(client, urls["confirm"], b"not-json")
        assert r.status_code == 200
        assert r.json()["event_status"] == "UNPROCESSABLE"
        assert _events(db)[0].status == PaymentEventStatus.UNPROCESSABLE


class TestC2BAdapterIntegration:
    def test_real_adapter_parse_and_service_agree(self, client, db):
        """The endpoint path runs the real Daraja parser end to end."""
        headers, chama, conn, urls = _setup(client)
        _activate(client, headers, chama, conn)
        r = _post(client, urls["confirm"], _c2b_payload(bill_ref="1"))
        assert r.status_code == 200
        event = _events(db)[0]
        assert event.connection_id == uuid.UUID(conn["id"])
        assert event.provider_event_id == "C2B_CONFIRMATION:RKTQDM7W6w"


@pytest.fixture
def fake_daraja():
    fake = setup_fake_adapter(PaymentProviderCode.DARAJA, PaymentEnvironment.SANDBOX)
    yield fake
    restore_fake_adapter(PaymentProviderCode.DARAJA, PaymentEnvironment.SANDBOX)


def _register_url(chama_id: str, connection_id: str) -> str:
    return f"/api/v1/chamas/{chama_id}/payment-connections/{connection_id}/register-c2b-urls"


class TestC2BRegisterUrls:
    def test_register_urls_success(self, client, db, fake_daraja):
        headers, chama, conn, _ = _setup(client)
        r = client.post(
            _register_url(chama["id"], conn["id"]),
            headers=headers,
            json={"response_type": "Completed"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["accepted"] is True
        assert data["response_code"] == "0"
        token = connection_callback_token(
            connection_id=uuid.UUID(conn["id"]),
            provider_code=PaymentProviderCode.DARAJA,
            environment=PaymentEnvironment.SANDBOX,
        )
        expected_validate = f"/payments/c2b/validate/{conn['id']}?token={token}"
        expected_confirm = f"/payments/c2b/confirm/{conn['id']}?token={token}"
        assert data["validation_url"].endswith(expected_validate)
        assert data["confirmation_url"].endswith(expected_confirm)
        assert fake_daraja.last_register_request is not None
        assert fake_daraja.last_register_request.short_code == "600598"

    def test_register_urls_requires_chairperson(self, client, db, fake_daraja):
        headers, chama, conn, _ = _setup(client)
        member = register_and_login(client, "member-c2b@e.com")
        client.post(
            f"/api/v1/chamas/{chama['id']}/memberships",
            headers=headers,
            json={
                "member": {
                    "first_name": "Bob",
                    "last_name": "Kimani",
                    "phone_number": "+254700000202",
                    "government_id": "GID-202",
                }
            },
        )
        r = client.post(
            _register_url(chama["id"], conn["id"]),
            headers=member,
            json={"response_type": "Completed"},
        )
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "PERMISSION_DENIED"

    def test_register_urls_provider_rejection_reported(self, client, db, fake_daraja):
        headers, chama, conn, _ = _setup(client)
        fake_daraja.register_c2b_error = ProviderIntegrationError(
            "C2B_REGISTER_FAILED_3", "shortcode not enabled"
        )
        r = client.post(
            _register_url(chama["id"], conn["id"]),
            headers=headers,
            json={"response_type": "Completed"},
        )
        assert r.status_code == 400
        assert "C2B_REGISTER_FAILED_3" in r.json()["detail"]["message"]

    def test_register_urls_unknown_connection_rejected(self, client, db, fake_daraja):
        headers, chama, conn, _ = _setup(client)
        r = client.post(
            _register_url(chama["id"], str(uuid.uuid4())),
            headers=headers,
            json={"response_type": "Completed"},
        )
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "INVALID_STATE"