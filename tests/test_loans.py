"""Loan lifecycle tests (ADR-020)."""

import uuid
from datetime import datetime, timedelta

import pytest

from tests.conftest import add_membership, create_chama, register_and_login

PERIOD = "2026-09"


def _backdate(db, membership_id, days=40):
    from app.models.membership import Membership

    membership = db.get(Membership, uuid.UUID(membership_id))
    membership.joined_at = datetime.now() - timedelta(days=days)
    db.commit()


def _link_bob(client, email="bob@e.com", phone="+254700000099", govt="GID-099"):
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


def _ledger_balance(client, headers, chama_id, code):
    r = client.get(f"/api/v1/chamas/{chama_id}/ledger/accounts", headers=headers)
    assert r.status_code == 200, r.json()
    for item in r.json()["items"]:
        if item["code"] == code:
            return item["balance"]
    raise AssertionError(f"account {code} not found")


class TestLoanLifecycle:
    def _setup(self, client, db):
        chair = register_and_login(client, "chair-loan@e.com")
        chama = create_chama(client, chair)
        bob = add_membership(client, chair, chama["id"], phone="+254700000099", govt="GID-099")
        bob_headers = _link_bob(client)
        _backdate(db, bob["id"])
        # cash in the Chama and share value for Bob
        _fund(client, chair, chama["id"], bob["id"], 6000)
        return chair, chama, bob, bob_headers

    def test_apply_requires_one_month_tenure(self, client, db):
        chair = register_and_login(client, "chair-loan1@e.com")
        chama = create_chama(client, chair)
        bob = add_membership(client, chair, chama["id"], phone="+254700000199", govt="GID-199")
        bob_headers = _link_bob(client, email="bob1@e.com", phone="+254700000199", govt="GID-199")
        _fund(client, chair, chama["id"], bob["id"], 6000)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/loans",
            headers=bob_headers,
            json={"principal": "1000.00", "term_months": 6},
        )
        assert r.status_code == 400
        assert "one month" in r.json()["detail"]["message"]

    def test_full_loan_lifecycle_posts_ledger(self, client, db):
        chair, chama, bob, bob_headers = self._setup(client, db)

        r = client.post(
            f"/api/v1/chamas/{chama['id']}/loans",
            headers=bob_headers,
            json={"principal": "3000.00", "term_months": 6},
        )
        assert r.status_code == 201, r.json()
        loan = r.json()
        assert loan["status"] == "DRAFT"
        assert loan["total_interest"] == "150.00"
        assert loan["outstanding_principal"] == "3000.00"

        loan_id = loan["id"]

        r = client.post(f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/submit", headers=bob_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "SUBMITTED"

        r = client.post(f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/approve", headers=chair)
        assert r.status_code == 200, r.json()
        assert r.json()["status"] == "APPROVED"
        assert r.json()["approved_by_user_id"] is not None

        r = client.post(f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/disburse", headers=chair)
        assert r.status_code == 200, r.json()
        assert r.json()["status"] == "DISBURSED"
        assert r.json()["maturity_date"] is not None

        assert _ledger_balance(client, chair, chama["id"], "1000") == "3000.00"
        assert _ledger_balance(client, chair, chama["id"], "1100") == "3000.00"

    def test_approval_is_idempotent_on_retry(self, client, db):
        chair, chama, bob, bob_headers = self._setup(client, db)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/loans",
            headers=bob_headers,
            json={"principal": "1000.00", "term_months": 3},
        )
        loan_id = r.json()["id"]
        client.post(f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/submit", headers=bob_headers)
        client.post(f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/approve", headers=chair)
        r = client.post(f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/disburse", headers=chair)
        assert r.status_code == 200
        r2 = client.post(f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/disburse", headers=chair)
        assert r2.status_code == 200
        assert r2.json()["status"] == "DISBURSED"
        assert _ledger_balance(client, chair, chama["id"], "1100") == "1000.00"

    def test_principal_limited_to_three_times_share_value(self, client, db):
        chair, chama, bob, bob_headers = self._setup(client, db)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/loans",
            headers=bob_headers,
            json={"principal": "20000.00", "term_months": 6},
        )
        assert r.status_code == 400
        assert "three times" in r.json()["detail"]["message"]

    def test_principal_limited_to_available_cash(self, client, db):
        chair = register_and_login(client, "chair-loan2@e.com")
        chama = create_chama(client, chair)
        bob = add_membership(client, chair, chama["id"], phone="+254700000299", govt="GID-299")
        bob_headers = _link_bob(client, email="bob2@e.com", phone="+254700000299", govt="GID-299")
        _backdate(db, bob["id"])
        # share value 2000 (3x = 6000) passes, but available cash only 2000
        _fund(client, chair, chama["id"], bob["id"], 2000)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/loans",
            headers=bob_headers,
            json={"principal": "3000.00", "term_months": 6},
        )
        assert r.status_code == 400
        assert "available cash" in r.json()["detail"]["message"]

    def test_member_cannot_approve_own_loan(self, client, db):
        chair = register_and_login(client, "chair-loan5@e.com")
        chama = create_chama(client, chair)
        # find the chair's own membership (creator)
        r = client.get(f"/api/v1/chamas/{chama['id']}/memberships", headers=chair)
        assert r.status_code == 200
        chair_membership_id = r.json()[0]["id"]
        _backdate(db, chair_membership_id)
        _fund(client, chair, chama["id"], chair_membership_id, 6000)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/loans",
            headers=chair,
            json={"principal": "1000.00", "term_months": 3},
        )
        assert r.status_code == 201, r.json()
        loan_id = r.json()["id"]
        r = client.post(f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/submit", headers=chair)
        assert r.status_code == 200
        r = client.post(f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/approve", headers=chair)
        assert r.status_code == 400
        assert "own loan" in r.json()["detail"]["message"]

    def test_non_member_of_chama_cannot_apply(self, client, db):
        chair = register_and_login(client, "chair-loan3@e.com")
        chama = create_chama(client, chair)
        outsider = register_and_login(client, "outsider@e.com")
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/loans",
            headers=outsider,
            json={"principal": "1000.00", "term_months": 3},
        )
        assert r.status_code == 403

    def test_cancel_approved_loan(self, client, db):
        chair, chama, bob, bob_headers = self._setup(client, db)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/loans",
            headers=bob_headers,
            json={"principal": "1000.00", "term_months": 3},
        )
        loan_id = r.json()["id"]
        client.post(f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/submit", headers=bob_headers)
        client.post(f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/approve", headers=chair)
        r = client.post(f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/cancel", headers=chair)
        assert r.status_code == 200
        assert r.json()["status"] == "CANCELLED"

    def test_rejected_loan_cannot_be_disbursed(self, client, db):
        chair, chama, bob, bob_headers = self._setup(client, db)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/loans",
            headers=bob_headers,
            json={"principal": "1000.00", "term_months": 3},
        )
        loan_id = r.json()["id"]
        client.post(f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/submit", headers=bob_headers)
        r = client.post(f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/reject", headers=chair)
        assert r.status_code == 200
        assert r.json()["status"] == "REJECTED"
        r = client.post(f"/api/v1/chamas/{chama['id']}/loans/{loan_id}/disburse", headers=chair)
        assert r.status_code == 400
        assert "cannot transition" in r.json()["detail"]["message"]

    def test_cross_chama_loan_is_hidden(self, client, db):
        chair = register_and_login(client, "chair-loan4@e.com")
        chama = create_chama(client, chair)
        bob = add_membership(client, chair, chama["id"], phone="+254700000399", govt="GID-399")
        bob_headers = _link_bob(client, email="bob3@e.com", phone="+254700000399", govt="GID-399")
        _backdate(db, bob["id"])
        _fund(client, chair, chama["id"], bob["id"], 6000)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/loans",
            headers=bob_headers,
            json={"principal": "1000.00", "term_months": 3},
        )
        loan_id = r.json()["id"]
        other = create_chama(
            client,
            register_and_login(client, "other@e.com"),
            name="Other Chama",
            phone="+254700000444",
            govt="GID-444",
        )
        r = client.post(
            f"/api/v1/chamas/{other['id']}/loans/{loan_id}/submit",
            headers=register_and_login(client, "othermem@e.com"),
        )
        assert r.status_code in (403, 404)