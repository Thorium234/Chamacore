"""Loan repayment tests (ADR-020 repayment allocation)."""

import uuid
from datetime import datetime, timedelta

import pytest

from tests.conftest import add_membership, create_chama, register_and_login

PERIOD = "2026-10"


def _backdate(db, membership_id, days=40):
    from app.models.membership import Membership

    membership = db.get(Membership, uuid.UUID(membership_id))
    membership.joined_at = datetime.now() - timedelta(days=days)
    db.commit()


def _link_member(client, email="bob@e.com", phone="+254700000699", govt="GID-699"):
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


def _disbursed_loan(client, db, *, principal="3000.00"):
    chair = register_and_login(client, "chair-repay@e.com")
    chama = create_chama(client, chair)
    bob = add_membership(client, chair, chama["id"], phone="+254700000699", govt="GID-699")
    bob_headers = _link_member(client)
    _backdate(db, bob["id"])
    _fund(client, chair, chama["id"], bob["id"], 6000)
    r = client.post(
        f"/api/v1/chamas/{chama['id']}/loans",
        headers=bob_headers,
        json={"principal": principal, "term_months": 6},
    )
    assert r.status_code == 201, r.json()
    loan_id = r.json()["id"]
    client.post(f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/submit", headers=bob_headers)
    client.post(f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/approve", headers=chair)
    r = client.post(f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/disburse", headers=chair)
    assert r.status_code == 200, r.json()
    return chair, chama, bob, loan_id


def _balances(client, headers, chama_id):
    r = client.get(f"/api/v1/chamas/{chama_id}/ledger/accounts", headers=headers)
    assert r.status_code == 200
    return {item["code"]: item["balance"] for item in r.json()["items"]}


class TestLoanRepayments:
    def test_partial_repayment_interest_first(self, client, db):
        chair, chama, bob, loan_id = _disbursed_loan(client, db)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/repayments",
            headers=chair,
            json={"amount": "1000.00"},
        )
        assert r.status_code == 201, r.json()
        loan = r.json()
        assert loan["status"] == "PARTIALLY_REPAID"
        assert loan["outstanding_principal"] == "2150.00"
        assert loan["outstanding_interest"] == "0.00"
        bal = _balances(client, chair, chama["id"])
        assert bal["1000"] == "4000.00"
        assert bal["1100"] == "2150.00"
        assert bal["5000"] == "-150.00"
        assert bal["3000"] == "-6000.00"

    def test_full_repayment_reaches_repaid(self, client, db):
        chair, chama, bob, loan_id = _disbursed_loan(client, db)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/repayments",
            headers=chair,
            json={"amount": "3150.00"},
        )
        assert r.status_code == 201, r.json()
        assert r.json()["status"] == "REPAID"
        assert r.json()["outstanding_principal"] == "0.00"
        assert r.json()["outstanding_interest"] == "0.00"

    def test_overpayment_rejected(self, client, db):
        chair, chama, bob, loan_id = _disbursed_loan(client, db)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/repayments",
            headers=chair,
            json={"amount": "4000.00"},
        )
        assert r.status_code == 400
        assert "exceeds" in r.json()["detail"]["message"]

    def test_repayment_requires_leadership_role(self, client, db):
        chair, chama, bob, loan_id = _disbursed_loan(client, db)
        member = register_and_login(client, "plainmember@e.com")
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/repayments",
            headers=member,
            json={"amount": "100.00"},
        )
        assert r.status_code == 403

    def test_repayment_on_undisbursed_loan_rejected(self, client, db):
        chair = register_and_login(client, "chair-repay2@e.com")
        chama = create_chama(client, chair)
        bob = add_membership(client, chair, chama["id"], phone="+254700000799", govt="GID-799")
        bob_headers = _link_member(client, email="bob2@e.com", phone="+254700000799", govt="GID-799")
        _backdate(db, bob["id"])
        _fund(client, chair, chama["id"], bob["id"], 6000)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/loans",
            headers=bob_headers,
            json={"principal": "1000.00", "term_months": 3},
        )
        loan_id = r.json()["id"]
        client.post(f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/submit", headers=bob_headers)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/repayments",
            headers=chair,
            json={"amount": "100.00"},
        )
        assert r.status_code == 400
        assert "disbursed" in r.json()["detail"]["message"]

    def test_reverse_repayment_restores_outstanding_and_ledger(self, client, db):
        chair, chama, bob, loan_id = _disbursed_loan(client, db)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/repayments",
            headers=chair,
            json={"amount": "1000.00"},
        )
        repayment_id = self._last_repayment_id(client, chair, chama["id"], loan_id)
        assert repayment_id is not None

        r = client.post(
            f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/repayments/{repayment_id}/reverse",
            headers=chair,
            json={"note": "wrong entry"},
        )
        assert r.status_code == 200, r.json()
        loan = r.json()
        assert loan["status"] == "DISBURSED"
        assert loan["outstanding_principal"] == "3000.00"
        assert loan["outstanding_interest"] == "150.00"
        bal = _balances(client, chair, chama["id"])
        assert bal["1000"] == "3000.00"
        assert bal["1100"] == "3000.00"
        assert bal["5000"] == "0.00"

        # the loan can receive repayments again
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/repayments",
            headers=chair,
            json={"amount": "3150.00"},
        )
        assert r.status_code == 201
        assert r.json()["status"] == "REPAID"

    def test_repaid_loan_accepts_no_more_repayments(self, client, db):
        chair, chama, bob, loan_id = _disbursed_loan(client, db)
        client.post(
            f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/repayments",
            headers=chair,
            json={"amount": "3150.00"},
        )
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/repayments",
            headers=chair,
            json={"amount": "100.00"},
        )
        assert r.status_code == 400

    @staticmethod
    def _last_repayment_id(client, headers, chama_id, loan_id):
        r = client.get(f"/api/v1/chamas/{chama_id}/loans/{loan_id}/repayments", headers=headers)
        assert r.status_code == 200
        items = r.json()
        return items[-1]["id"] if items else None