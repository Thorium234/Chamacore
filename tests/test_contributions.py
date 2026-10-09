"""Contribution and share tests."""

import uuid

import pytest
from sqlalchemy import select

from app.models.ledger_transaction import LedgerTransaction
from app.services.ledger import CONTRIBUTION_SOURCE_TYPE, REVERSAL_SOURCE_TYPE
from tests.conftest import register_and_login, create_chama, add_membership


def _ledger(db):
    return list(db.scalars(select(LedgerTransaction).order_by(LedgerTransaction.created_at)))


def _setup_contributing_chama(client):
    """Return (headers_chair, chama, membership) with a second membership ready."""
    headers = register_and_login(client, "chair@e.com")
    chama = create_chama(client, headers, fee="0.00")
    members = add_membership(client, headers, chama["id"], phone="+254700000600", govt="GID-600")
    return headers, chama, members


class TestRecordContribution:
    def test_chairperson_can_record(self, client):
        headers, chama, m = _setup_contributing_chama(client)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": m["id"], "amount": "2000.00", "period": "2026-09"},
        )
        assert r.status_code == 201
        assert r.json()["status"] == "PENDING"
        assert r.json()["amount"] == "2000.00"
        assert r.json()["period"] == "2026-09"

    def test_treasurer_can_record(self, client):
        headers_chair = register_and_login(client, "chair@e.com")
        chama = create_chama(client, headers_chair, fee="0.00")
        m = add_membership(client, headers_chair, chama["id"], phone="+254700000610", govt="GID-610")
        # add treasurer member and assign TREASURER role
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/memberships",
            headers=headers_chair,
            json={"member": {"first_name": "T", "last_name": "R", "phone_number": "+254700000620", "government_id": "GID-620", "email": "treasurer@example.com"}},
        )
        treas_id = r.json()["id"]
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/memberships/{treas_id}/roles",
            headers=headers_chair,
            json={"role": "TREASURER"},
        )
        assert r.status_code == 201
        # New member accounts are linked on creation and must change their
        # government-ID password before using protected Chama endpoints.
        r = client.post(
            "/api/v1/auth/token",
            data={"username": "+254700000620", "password": "GID-620"},
        )
        assert r.status_code == 200, r.json()
        headers_treas = {"Authorization": f"Bearer {r.json()['access_token']}"}
        changed = client.post(
            "/api/v1/auth/change-password",
            headers=headers_treas,
            json={"current_password": "GID-620", "new_password": "MemberChangedPass123!"},
        )
        assert changed.status_code == 200, changed.json()
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers_treas,
            json={"membership_id": m["id"], "amount": "1500.00", "period": "2026-09"},
        )
        assert r.status_code == 201

    def test_ordinary_member_cannot_record(self, client):
        headers_chair = register_and_login(client, "chair@e.com")
        chama = create_chama(client, headers_chair, fee="0.00")
        m = add_membership(client, headers_chair, chama["id"], phone="+254700000630", govt="GID-630")
        r = client.post(
            "/api/v1/auth/token",
            data={"username": "+254700000630", "password": "GID-630"},
        )
        assert r.status_code == 200, r.json()
        headers_mem = {"Authorization": f"Bearer {r.json()['access_token']}"}
        changed = client.post(
            "/api/v1/auth/change-password",
            headers=headers_mem,
            json={"current_password": "GID-630", "new_password": "MemberChangedPass123!"},
        )
        assert changed.status_code == 200, changed.json()
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers_mem,
            json={"membership_id": m["id"], "amount": "1000.00", "period": "2026-09"},
        )
        assert r.status_code == 403

    def test_duplicate_period_rejected(self, client):
        headers, chama, m = _setup_contributing_chama(client)
        client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": m["id"], "amount": "1000.00", "period": "2026-09"},
        )
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": m["id"], "amount": "500.00", "period": "2026-09"},
        )
        assert r.status_code == 409

    def test_negative_amount_rejected(self, client):
        headers, chama, m = _setup_contributing_chama(client)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": m["id"], "amount": "-100", "period": "2026-09"},
        )
        assert r.status_code == 422

    def test_invalid_period_rejected(self, client):
        headers, chama, m = _setup_contributing_chama(client)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": m["id"], "amount": "1000.00", "period": "invalid"},
        )
        assert r.status_code == 422

    def test_valid_period_13_rejected(self, client):
        headers, chama, m = _setup_contributing_chama(client)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": m["id"], "amount": "1000.00", "period": "2026-13"},
        )
        assert r.status_code == 422

    def test_payment_date_is_optional_and_returned(self, client):
        headers, chama, m = _setup_contributing_chama(client)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": m["id"], "amount": "1000.00", "period": "2026-09"},
        )
        assert r.status_code == 201
        assert r.json()["payment_date"] is None

    def test_payment_date_recorded(self, client):
        headers, chama, m = _setup_contributing_chama(client)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={
                "membership_id": m["id"],
                "amount": "1000.00",
                "period": "2026-09",
                "payment_date": "2026-09-05",
            },
        )
        assert r.status_code == 201, r.json()
        assert r.json()["payment_date"] == "2026-09-05"
        listed = client.get(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
        ).json()
        assert listed[0]["payment_date"] == "2026-09-05"

    def test_payment_date_invalid_value_rejected(self, client):
        headers, chama, m = _setup_contributing_chama(client)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={
                "membership_id": m["id"],
                "amount": "1000.00",
                "period": "2026-09",
                "payment_date": "05/09/2026",
            },
        )
        assert r.status_code == 422

    def test_payment_date_does_not_change_ledger_effect(self, client, db):
        headers, chama, m = _setup_contributing_chama(client)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={
                "membership_id": m["id"],
                "amount": "1000.00",
                "period": "2026-09",
                "payment_date": "2026-09-05",
            },
        )
        contrib_id = r.json()["id"]
        confirmed = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions/{contrib_id}/confirm",
            headers=headers,
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["payment_date"] == "2026-09-05"
        postings = [t for t in _ledger(db) if t.source_type == CONTRIBUTION_SOURCE_TYPE]
        assert len(postings) == 1
        assert sum(e.debit for t in postings for e in t.entries) == 1000


class TestConfirmContribution:
    def test_confirm_creates_shares_and_posts_ledger(self, client, db):
        headers, chama, m = _setup_contributing_chama(client)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": m["id"], "amount": "3000.00", "period": "2026-09"},
        )
        contrib_id = r.json()["id"]
        r = client.post(f"/api/v1/chamas/{chama['id']}/contributions/{contrib_id}/confirm", headers=headers)
        assert r.status_code == 200
        assert r.json()["status"] == "CONFIRMED"
        assert r.json()["confirmed_at"] is not None
        # verify shares exist
        r = client.get(
            f"/api/v1/chamas/{chama['id']}/memberships/{m['id']}/shares",
            headers=headers,
        )
        assert r.status_code == 200
        shares = r.json()
        assert len(shares) >= 1
        assert shares[0]["units"] == "30.0000"  # 3000 / 100
        # OQ-013: one balanced posting, DR Cash / CR Share Capital
        postings = [t for t in _ledger(db) if t.source_type == CONTRIBUTION_SOURCE_TYPE]
        assert len(postings) == 1
        assert postings[0].source_id == uuid.UUID(contrib_id)
        posts = sum(e.debit for t in postings for e in t.entries)
        credits = sum(e.credit for t in postings for e in t.entries)
        assert posts == 3000 and credits == 3000

    def test_reconfirm_is_idempotent_retry(self, client, db):
        headers, chama, m = _setup_contributing_chama(client)
        client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": m["id"], "amount": "1000.00", "period": "2026-09"},
        )
        contrib_id = client.get(
            f"/api/v1/chamas/{chama['id']}/contributions", headers=headers
        ).json()[0]["id"]
        client.post(f"/api/v1/chamas/{chama['id']}/contributions/{contrib_id}/confirm", headers=headers)
        second = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions/{contrib_id}/confirm", headers=headers
        )
        assert second.status_code == 400
        assert len(_ledger(db)) == 1

    def test_non_chairperson_cannot_confirm(self, client):
        headers_chair = register_and_login(client, "chair@e.com")
        chama = create_chama(client, headers_chair, fee="0.00")
        m = add_membership(client, headers_chair, chama["id"], phone="+254700000700", govt="GID-700")
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers_chair,
            json={"membership_id": m["id"], "amount": "1000.00", "period": "2026-09"},
        )
        contrib_id = r.json()["id"]
        # log in as ordinary member
        client.post("/api/v1/auth/register", json={"email": "nonchair@e.com", "password": "StrongTestPassword123!"})
        r = client.post("/api/v1/auth/token", data={"username": "nonchair@e.com", "password": "StrongTestPassword123!"})
        headers_non = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = client.post(f"/api/v1/chamas/{chama['id']}/contributions/{contrib_id}/confirm", headers=headers_non)
        assert r.status_code == 403

    def test_already_confirmed_rejected(self, client):
        headers, chama, m = _setup_contributing_chama(client)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": m["id"], "amount": "1000.00", "period": "2026-09"},
        )
        contrib_id = r.json()["id"]
        client.post(f"/api/v1/chamas/{chama['id']}/contributions/{contrib_id}/confirm", headers=headers)
        r = client.post(f"/api/v1/chamas/{chama['id']}/contributions/{contrib_id}/confirm", headers=headers)
        assert r.status_code == 400


class TestReverseContribution:
    def test_reverse_marks_shares_reversed(self, client):
        headers, chama, m = _setup_contributing_chama(client)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": m["id"], "amount": "5000.00", "period": "2026-09"},
        )
        contrib_id = r.json()["id"]
        client.post(f"/api/v1/chamas/{chama['id']}/contributions/{contrib_id}/confirm", headers=headers)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions/{contrib_id}/reverse",
            headers=headers,
            json={"note": "Wrong amount"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "REVERSED"
        assert r.json()["note"] == "Wrong amount"
        # shares reversed
        r = client.get(
            f"/api/v1/chamas/{chama['id']}/memberships/{m['id']}/shares",
            headers=headers,
        )
        assert all(s["status"] == "REVERSED" for s in r.json())

    def test_reverse_frees_period_for_new_contribution(self, client):
        headers, chama, m = _setup_contributing_chama(client)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": m["id"], "amount": "1000.00", "period": "2026-09"},
        )
        contrib_id = r.json()["id"]
        client.post(f"/api/v1/chamas/{chama['id']}/contributions/{contrib_id}/confirm", headers=headers)
        client.post(f"/api/v1/chamas/{chama['id']}/contributions/{contrib_id}/reverse", headers=headers, json={})
        # now can record a new contribution for the same period
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": m["id"], "amount": "2000.00", "period": "2026-09"},
        )
        assert r.status_code == 201

    def test_reverse_posts_compensating_ledger_reversal(self, client, db):
        headers, chama, m = _setup_contributing_chama(client)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": m["id"], "amount": "5000.00", "period": "2026-09"},
        )
        contrib_id = r.json()["id"]
        client.post(f"/api/v1/chamas/{chama['id']}/contributions/{contrib_id}/confirm", headers=headers)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions/{contrib_id}/reverse",
            headers=headers,
            json={"note": "Wrong amount"},
        )
        assert r.status_code == 200
        txn = _ledger(db)
        assert len(txn) == 2
        posting, reversal = txn
        assert posting.source_type == CONTRIBUTION_SOURCE_TYPE
        assert reversal.source_type == REVERSAL_SOURCE_TYPE
        assert reversal.reverses_transaction_id == posting.id
        original = {(e.account_id, e.debit, e.credit) for e in posting.entries}
        mirrored = {(e.account_id, e.credit, e.debit) for e in reversal.entries}
        assert mirrored == original

    def test_pending_cannot_be_reversed(self, client):
        headers, chama, m = _setup_contributing_chama(client)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": m["id"], "amount": "1000.00", "period": "2026-09"},
        )
        contrib_id = r.json()["id"]
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions/{contrib_id}/reverse",
            headers=headers,
            json={},
        )
        assert r.status_code == 400


class TestListContributions:
    def test_list_contributions(self, client):
        headers, chama, m = _setup_contributing_chama(client)
        client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": m["id"], "amount": "1000.00", "period": "2026-09"},
        )
        r = client.get(f"/api/v1/chamas/{chama['id']}/contributions", headers=headers)
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_list_filters_by_membership(self, client):
        headers, chama, m = _setup_contributing_chama(client)
        chair_membership_id = chama["membership_id"]
        for period in ("2026-09", "2026-10"):
            client.post(
                f"/api/v1/chamas/{chama['id']}/contributions",
                headers=headers,
                json={"membership_id": m["id"], "amount": "1000.00", "period": period},
            )
        client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": chair_membership_id, "amount": "500.00", "period": "2026-09"},
        )
        r = client.get(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            params={"membership_id": m["id"]},
        )
        assert r.status_code == 200
        assert {c["membership_id"] for c in r.json()} == {m["id"]}
        assert len(r.json()) == 2

    def test_list_filters_by_period(self, client):
        headers, chama, m = _setup_contributing_chama(client)
        for period in ("2026-09", "2026-10"):
            client.post(
                f"/api/v1/chamas/{chama['id']}/contributions",
                headers=headers,
                json={"membership_id": m["id"], "amount": "1000.00", "period": period},
            )
        r = client.get(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            params={"period": "2026-10"},
        )
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["period"] == "2026-10"

    def test_list_filters_by_status(self, client):
        headers, chama, m = _setup_contributing_chama(client)
        pending = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": m["id"], "amount": "1000.00", "period": "2026-09"},
        ).json()
        confirmed = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": m["id"], "amount": "2000.00", "period": "2026-10"},
        ).json()
        client.post(
            f"/api/v1/chamas/{chama['id']}/contributions/{confirmed['id']}/confirm", headers=headers
        )
        r = client.get(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            params={"status": "PENDING"},
        )
        assert r.status_code == 200
        assert {c["id"] for c in r.json()} == {pending["id"]}
        r = client.get(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            params={"status": "CONFIRMED"},
        )
        assert {c["id"] for c in r.json()} == {confirmed["id"]}

    def test_list_invalid_period_rejected(self, client):
        headers, chama, m = _setup_contributing_chama(client)
        r = client.get(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            params={"period": "2026-13"},
        )
        assert r.status_code == 422

    def test_list_invalid_status_rejected(self, client):
        headers, chama, m = _setup_contributing_chama(client)
        r = client.get(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            params={"status": "DEFUNCT"},
        )
        assert r.status_code == 422

    def test_list_membership_from_another_chama_rejected(self, client):
        headers_a = register_and_login(client, "chair-a@e.com")
        chama_a = create_chama(client, headers_a, phone="+254700000811", govt="GID-811")
        headers_b = register_and_login(client, "chair-b@e.com")
        chama_b = create_chama(client, headers_b, phone="+254700000822", govt="GID-822")
        r = client.get(
            f"/api/v1/chamas/{chama_a['id']}/contributions",
            headers=headers_a,
            params={"membership_id": chama_b["membership_id"]},
        )
        assert r.status_code == 404

    def test_non_member_cannot_list(self, client):
        headers, chama, m = _setup_contributing_chama(client)
        client.post("/api/v1/auth/register", json={"email": "stranger@e.com", "password": "StrongTestPassword123!"})
        r = client.post("/api/v1/auth/token", data={"username": "stranger@e.com", "password": "StrongTestPassword123!"})
        headers_s = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = client.get(f"/api/v1/chamas/{chama['id']}/contributions", headers=headers_s)
        assert r.status_code == 403
