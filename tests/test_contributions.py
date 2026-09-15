"""Contribution and share tests."""

import pytest

from tests.conftest import register_and_login, create_chama, add_membership


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
            json={"member": {"first_name": "T", "last_name": "R", "phone_number": "+254700000620", "government_id": "GID-620"}},
        )
        treas_id = r.json()["id"]
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/memberships/{treas_id}/roles",
            headers=headers_chair,
            json={"role": "TREASURER"},
        )
        assert r.status_code == 201
        # treasurer registers and claims their member identity
        client.post("/api/v1/auth/register", json={"email": "t@e.com", "password": "password123"})
        r = client.post("/api/v1/auth/token", data={"username": "t@e.com", "password": "password123"})
        headers_treas = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = client.post(
            "/api/v1/auth/me/member-link",
            headers=headers_treas,
            json={"phone_number": "+254700000620", "government_id": "GID-620"},
        )
        assert r.status_code == 200, r.json()
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
        client.post("/api/v1/auth/register", json={"email": "mem@e.com", "password": "password123"})
        r = client.post("/api/v1/auth/token", data={"username": "mem@e.com", "password": "password123"})
        headers_mem = {"Authorization": f"Bearer {r.json()['access_token']}"}
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


class TestConfirmContribution:
    def test_confirm_creates_shares(self, client):
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
        client.post("/api/v1/auth/register", json={"email": "nonchair@e.com", "password": "password123"})
        r = client.post("/api/v1/auth/token", data={"username": "nonchair@e.com", "password": "password123"})
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

    def test_non_member_cannot_list(self, client):
        headers, chama, m = _setup_contributing_chama(client)
        client.post("/api/v1/auth/register", json={"email": "stranger@e.com", "password": "password123"})
        r = client.post("/api/v1/auth/token", data={"username": "stranger@e.com", "password": "password123"})
        headers_s = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = client.get(f"/api/v1/chamas/{chama['id']}/contributions", headers=headers_s)
        assert r.status_code == 403