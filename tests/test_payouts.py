"""Payout lifecycle tests (ADR-021)."""

import uuid

import pytest

from tests.conftest import add_membership, create_chama, register_and_login

PERIOD = "2026-11"


def _link_member(client, email="bob@e.com", phone="+254700000899", govt="GID-899"):
    headers = register_and_login(client, email)
    r = client.post(
        "/api/v1/auth/me/member-link",
        headers=headers,
        json={"phone_number": phone, "government_id": govt},
    )
    assert r.status_code == 200, r.json()
    return headers


def _fund(client, headers, chama_id, membership_id, amount, period=PERIOD):
    r = client.post(
        f"/api/v1/chamas/{chama_id}/contributions",
        headers=headers,
        json={"membership_id": membership_id, "amount": str(amount), "period": period},
    )
    assert r.status_code == 201, r.json()
    cid = r.json()["id"]
    r = client.post(f"/api/v1/chamas/{chama_id}/contributions/{cid}/confirm", headers=headers)
    assert r.status_code == 200, r.json()


def _balances(client, headers, chama_id):
    r = client.get(f"/api/v1/chamas/{chama_id}/ledger/accounts", headers=headers)
    assert r.status_code == 200
    return {item["code"]: item["balance"] for item in r.json()["items"]}


class TestPayoutLifecycle:
    def _setup(self, client):
        chair = register_and_login(client, "chair-payout@e.com")
        chama = create_chama(client, chair)
        bob = add_membership(client, chair, chama["id"], phone="+254700000899", govt="GID-899")
        bob_headers = _link_member(client)
        # Bob funds 4000 (share value 4000); chair funds nothing extra
        _fund(client, chair, chama["id"], bob["id"], 4000)
        return chair, chama, bob, bob_headers

    def test_full_payout_lifecycle_posts_ledger(self, client):
        chair, chama, bob, bob_headers = self._setup(client)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payouts",
            headers=bob_headers,
            json={"amount": "500.00"},
        )
        assert r.status_code == 201, r.json()
        payout_id = r.json()["id"]

        r = client.post(f"/api/v1/chamas/{chama['id']}/payouts/{payout_id}/approve", headers=chair)
        assert r.status_code == 200, r.json()
        assert r.json()["status"] == "APPROVED"

        r = client.post(f"/api/v1/chamas/{chama['id']}/payouts/{payout_id}/process", headers=chair)
        assert r.status_code == 200, r.json()
        assert r.json()["status"] == "PROCESSING"

        r = client.post(f"/api/v1/chamas/{chama['id']}/payouts/{payout_id}/complete", headers=chair)
        assert r.status_code == 200, r.json()
        assert r.json()["status"] == "COMPLETED"

        bal = _balances(client, chair, chama["id"])
        assert bal["1000"] == "3500.00"
        assert bal["3000"] == "-3500.00"

    def test_complete_is_idempotent(self, client):
        chair, chama, bob, bob_headers = self._setup(client)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payouts",
            headers=bob_headers,
            json={"amount": "200.00"},
        )
        payout_id = r.json()["id"]
        client.post(f"/api/v1/chamas/{chama['id']}/payouts/{payout_id}/approve", headers=chair)
        client.post(f"/api/v1/chamas/{chama['id']}/payouts/{payout_id}/process", headers=chair)
        client.post(f"/api/v1/chamas/{chama['id']}/payouts/{payout_id}/complete", headers=chair)
        r = client.post(f"/api/v1/chamas/{chama['id']}/payouts/{payout_id}/complete", headers=chair)
        assert r.status_code == 200
        assert r.json()["status"] == "COMPLETED"
        assert _balances(client, chair, chama["id"])["3000"] == "-3800.00"

    def test_amount_limited_to_share_value(self, client):
        chair, chama, bob, bob_headers = self._setup(client)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payouts",
            headers=bob_headers,
            json={"amount": "5000.00"},
        )
        assert r.status_code == 400
        assert "share value" in r.json()["detail"]["message"]

    def test_amount_limited_to_available_cash(self, client, db):
        from datetime import datetime, timedelta

        from app.models.membership import Membership

        chair = register_and_login(client, "chair-payout2@e.com")
        chama = create_chama(client, chair)
        bob = add_membership(client, chair, chama["id"], phone="+254700000999", govt="GID-999")
        bob_headers = _link_member(client, email="bob2@e.com", phone="+254700000999", govt="GID-999")
        membership = db.get(Membership, uuid.UUID(bob["id"]))
        membership.joined_at = datetime.now() - timedelta(days=40)
        db.commit()
        # share value 5000; cash 5000
        _fund(client, chair, chama["id"], bob["id"], 5000)
        # disburse a 2500 loan to Bob: cash drops to 2500, share value stays 5000
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/loans",
            headers=bob_headers,
            json={"principal": "2500.00", "term_months": 3},
        )
        assert r.status_code == 201, r.json()
        loan_id = r.json()["id"]
        client.post(f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/submit", headers=bob_headers)
        client.post(f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/approve", headers=chair)
        client.post(f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/disburse", headers=chair)
        assert _balances(client, chair, chama["id"])["1000"] == "2500.00"
        # payout 3000 passes the share limit but exceeds available cash
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payouts",
            headers=bob_headers,
            json={"amount": "3000.00"},
        )
        assert r.status_code == 400
        assert "available cash" in r.json()["detail"]["message"]

    def test_member_cannot_approve(self, client):
        chair, chama, bob, bob_headers = self._setup(client)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payouts",
            headers=bob_headers,
            json={"amount": "100.00"},
        )
        payout_id = r.json()["id"]
        r = client.post(f"/api/v1/chamas/{chama['id']}/payouts/{payout_id}/approve", headers=bob_headers)
        assert r.status_code == 403

    def test_member_cannot_approve_own_payout(self, client):
        chair = register_and_login(client, "chair-payout3@e.com")
        chama = create_chama(client, chair)
        r = client.get(f"/api/v1/chamas/{chama['id']}/memberships", headers=chair)
        assert r.status_code == 200
        chair_membership_id = r.json()[0]["id"]
        _fund(client, chair, chama["id"], chair_membership_id, 2000)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payouts",
            headers=chair,
            json={"amount": "100.00"},
        )
        payout_id = r.json()["id"]
        r = client.post(f"/api/v1/chamas/{chama['id']}/payouts/{payout_id}/approve", headers=chair)
        assert r.status_code == 400
        assert "own payout" in r.json()["detail"]["message"]

    def test_reject_then_status(self, client):
        chair, chama, bob, bob_headers = self._setup(client)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payouts",
            headers=bob_headers,
            json={"amount": "100.00"},
        )
        payout_id = r.json()["id"]
        r = client.post(f"/api/v1/chamas/{chama['id']}/payouts/{payout_id}/reject", headers=chair)
        assert r.status_code == 200
        assert r.json()["status"] == "REJECTED"
        r = client.post(f"/api/v1/chamas/{chama['id']}/payouts/{payout_id}/complete", headers=chair)
        assert r.status_code == 400

    def test_fail_requires_reason(self, client):
        chair, chama, bob, bob_headers = self._setup(client)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payouts",
            headers=bob_headers,
            json={"amount": "100.00"},
        )
        payout_id = r.json()["id"]
        client.post(f"/api/v1/chamas/{chama['id']}/payouts/{payout_id}/approve", headers=chair)
        client.post(f"/api/v1/chamas/{chama['id']}/payouts/{payout_id}/process", headers=chair)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payouts/{payout_id}/fail",
            headers=chair,
            json={"failure_reason": "account closed"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "FAILED"
        assert r.json()["failure_reason"] == "account closed"

    def test_reverse_completed_payout(self, client):
        chair, chama, bob, bob_headers = self._setup(client)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payouts",
            headers=bob_headers,
            json={"amount": "200.00"},
        )
        payout_id = r.json()["id"]
        client.post(f"/api/v1/chamas/{chama['id']}/payouts/{payout_id}/approve", headers=chair)
        client.post(f"/api/v1/chamas/{chama['id']}/payouts/{payout_id}/process", headers=chair)
        client.post(f"/api/v1/chamas/{chama['id']}/payouts/{payout_id}/complete", headers=chair)

        r = client.post(f"/api/v1/chamas/{chama['id']}/payouts/{payout_id}/reverse", headers=chair)
        assert r.status_code == 200, r.json()
        assert r.json()["status"] == "REVERSED"
        bal = _balances(client, chair, chama["id"])
        assert bal["1000"] == "4000.00"
        assert bal["3000"] == "-4000.00"

    def test_payout_cannot_reverse_before_completion(self, client):
        chair, chama, bob, bob_headers = self._setup(client)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/payouts",
            headers=bob_headers,
            json={"amount": "100.00"},
        )
        payout_id = r.json()["id"]
        r = client.post(f"/api/v1/chamas/{chama['id']}/payouts/{payout_id}/reverse", headers=chair)
        assert r.status_code == 400
        assert "COMPLETED" in r.json()["detail"]["message"]