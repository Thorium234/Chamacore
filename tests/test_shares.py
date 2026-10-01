"""Chama-wide shares list tests (strategic plan W0/B1)."""

from tests.conftest import register_and_login, create_chama, add_membership


def _setup(client):
    headers = register_and_login(client, "chair@e.com")
    chama = create_chama(client, headers, fee="0.00")
    return headers, chama


def _record_and_confirm(client, headers, chama_id, membership_id, amount, period):
    rid = client.post(
        f"/api/v1/chamas/{chama_id}/contributions",
        headers=headers,
        json={"membership_id": membership_id, "amount": amount, "period": period},
    ).json()["id"]
    r = client.post(f"/api/v1/chamas/{chama_id}/contributions/{rid}/confirm", headers=headers)
    assert r.status_code == 200
    return rid


class TestListChamaShares:
    def test_chama_wide_list_contains_all_memberships(self, client):
        headers, chama = _setup(client)
        m = add_membership(client, headers, chama["id"], phone="+254700000600", govt="GID-600")
        chair_membership_id = chama["membership_id"]
        _record_and_confirm(client, headers, chama["id"], m["id"], "2000.00", "2026-09")
        _record_and_confirm(client, headers, chama["id"], chair_membership_id, "500.00", "2026-10")
        r = client.get(f"/api/v1/chamas/{chama['id']}/shares", headers=headers)
        assert r.status_code == 200
        memberships = {s["membership_id"] for s in r.json()}
        assert memberships == {m["id"], chair_membership_id}

    def test_unconfirmed_contributions_create_no_shares(self, client):
        headers, chama = _setup(client)
        m = add_membership(client, headers, chama["id"], phone="+254700000601", govt="GID-601")
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": m["id"], "amount": "1000.00", "period": "2026-09"},
        )
        assert r.status_code == 201
        r = client.get(f"/api/v1/chamas/{chama['id']}/shares", headers=headers)
        assert r.json() == []

    def test_reversed_share_still_listed(self, client):
        headers, chama = _setup(client)
        m = add_membership(client, headers, chama["id"], phone="+254700000602", govt="GID-602")
        rid = _record_and_confirm(client, headers, chama["id"], m["id"], "3000.00", "2026-09")
        client.post(
            f"/api/v1/chamas/{chama['id']}/contributions/{rid}/reverse",
            headers=headers,
            json={"note": "Wrong amount"},
        )
        r = client.get(f"/api/v1/chamas/{chama['id']}/shares", headers=headers)
        assert r.status_code == 200
        assert [s["status"] for s in r.json()] == ["REVERSED"]

    def test_chama_wide_list_paginates(self, client):
        headers, chama = _setup(client)
        period = "2026-09"
        for i, phone in enumerate(("+254700000603", "+254700000604", "+254700000605")):
            m = add_membership(client, headers, chama["id"], phone=phone, govt=f"GID-60{i}")
            _record_and_confirm(client, headers, chama["id"], m["id"], "1000.00", period)
        page1 = client.get(
            f"/api/v1/chamas/{chama['id']}/shares", headers=headers, params={"limit": 2}
        )
        page2 = client.get(
            f"/api/v1/chamas/{chama['id']}/shares",
            headers=headers,
            params={"limit": 2, "offset": 2},
        )
        assert page1.status_code == 200 and len(page1.json()) == 2
        assert page2.status_code == 200 and len(page2.json()) == 1
        seen = {s["membership_id"] for s in page1.json() + page2.json()}
        assert len(seen) == 3

    def test_non_member_cannot_list(self, client):
        _, chama = _setup(client)
        client.post("/api/v1/auth/register", json={"email": "stranger@e.com", "password": "password123"})
        r = client.post("/api/v1/auth/token", data={"username": "stranger@e.com", "password": "password123"})
        headers_s = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = client.get(f"/api/v1/chamas/{chama['id']}/shares", headers=headers_s)
        assert r.status_code == 403