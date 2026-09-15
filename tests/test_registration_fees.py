"""Registration fee tests."""

import pytest

from tests.conftest import register_and_login, create_chama, add_membership


class TestRegistrationFee:
    def test_fee_created_with_chama_amount(self, client):
        headers = register_and_login(client)
        chama = create_chama(client, headers, fee="250.00")
        m = add_membership(client, headers, chama["id"], phone="+254700000500", govt="GID-500")
        r = client.get(
            f"/api/v1/chamas/{chama['id']}/memberships/{m['id']}/registration-fee",
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["amount"] == "250.00"
        assert r.json()["status"] == "OWED"

    def test_chairperson_can_waive_fee(self, client):
        headers = register_and_login(client)
        chama = create_chama(client, headers, fee="50.00")
        m = add_membership(client, headers, chama["id"], phone="+254700000510", govt="GID-510")
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/memberships/{m['id']}/registration-fee/waive",
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "WAIVED"

    def test_already_waived_cannot_waive_again(self, client):
        headers = register_and_login(client)
        chama = create_chama(client, headers)
        m = add_membership(client, headers, chama["id"], phone="+254700000520", govt="GID-520")
        client.post(
            f"/api/v1/chamas/{chama['id']}/memberships/{m['id']}/registration-fee/waive",
            headers=headers,
        )
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/memberships/{m['id']}/registration-fee/waive",
            headers=headers,
        )
        assert r.status_code == 400

    def test_non_chairperson_cannot_waive(self, client):
        headers = register_and_login(client, "chair@e.com")
        chama = create_chama(client, headers)
        m = add_membership(client, headers, chama["id"], phone="+254700000530", govt="GID-530")
        headers_member = register_and_login(client, "mem@e.com")
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/memberships/{m['id']}/registration-fee/waive",
            headers=headers_member,
        )
        assert r.status_code == 403

    def test_zero_fee_still_creates_record(self, client):
        headers = register_and_login(client)
        chama = create_chama(client, headers, fee="0.00")
        m = add_membership(client, headers, chama["id"], phone="+254700000540", govt="GID-540")
        r = client.get(
            f"/api/v1/chamas/{chama['id']}/memberships/{m['id']}/registration-fee",
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["amount"] == "0.00"
        assert r.json()["status"] == "OWED"