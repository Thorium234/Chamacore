"""Role assignment tests."""

import pytest

from tests.conftest import register_and_login, create_chama, add_membership


class TestListRoles:
    def test_list_roles(self, client):
        headers = register_and_login(client)
        chama = create_chama(client, headers)
        r = client.get(f"/api/v1/chamas/{chama['id']}/roles", headers=headers)
        assert r.status_code == 200
        names = {role["name"] for role in r.json()}
        assert names == {"CHAIRPERSON", "TREASURER", "SECRETARY", "MEMBER"}


class TestAssignRole:
    def test_chairperson_can_assign_secretary(self, client):
        headers = register_and_login(client, "chair@e.com")
        chama = create_chama(client, headers)
        m = add_membership(client, headers, chama["id"], phone="+254700000400", govt="GID-400")
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/memberships/{m['id']}/roles",
            headers=headers,
            json={"role": "SECRETARY"},
        )
        assert r.status_code == 201
        assert "SECRETARY" in r.json()["roles"]
        assert "MEMBER" in r.json()["roles"]

    def test_chairperson_can_assign_treasurer(self, client):
        headers = register_and_login(client, "chair@e.com")
        chama = create_chama(client, headers)
        m = add_membership(client, headers, chama["id"], phone="+254700000410", govt="GID-410")
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/memberships/{m['id']}/roles",
            headers=headers,
            json={"role": "TREASURER"},
        )
        assert r.status_code == 201
        assert "TREASURER" in r.json()["roles"]

    def test_non_chairperson_cannot_assign_role(self, client):
        headers_chair = register_and_login(client, "chair@e.com")
        chama = create_chama(client, headers_chair)
        m = add_membership(client, headers_chair, chama["id"], phone="+254700000420", govt="GID-420")
        headers_member = register_and_login(client, "mem@e.com")
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/memberships/{m['id']}/roles",
            headers=headers_member,
            json={"role": "SECRETARY"},
        )
        assert r.status_code == 403

    def test_cannot_assign_manual_member_role(self, client):
        headers = register_and_login(client, "chair@e.com")
        chama = create_chama(client, headers)
        m = add_membership(client, headers, chama["id"], phone="+254700000430", govt="GID-430")
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/memberships/{m['id']}/roles",
            headers=headers,
            json={"role": "MEMBER"},
        )
        assert r.status_code == 400

    def test_second_chairperson_rejected(self, client):
        headers = register_and_login(client, "chair@e.com")
        chama = create_chama(client, headers)
        m = add_membership(client, headers, chama["id"], phone="+254700000440", govt="GID-440")
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/memberships/{m['id']}/roles",
            headers=headers,
            json={"role": "CHAIRPERSON"},
        )
        assert r.status_code == 400
        assert "already has a chairperson" in r.json()["detail"]["message"].lower()

    def test_second_leadership_role_rejected(self, client):
        headers = register_and_login(client, "chair@e.com")
        chama = create_chama(client, headers)
        m = add_membership(client, headers, chama["id"], phone="+254700000450", govt="GID-450")
        client.post(
            f"/api/v1/chamas/{chama['id']}/memberships/{m['id']}/roles",
            headers=headers,
            json={"role": "SECRETARY"},
        )
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/memberships/{m['id']}/roles",
            headers=headers,
            json={"role": "TREASURER"},
        )
        assert r.status_code == 400


class TestRemoveRole:
    def test_chairperson_can_remove_secretary(self, client):
        headers = register_and_login(client, "chair@e.com")
        chama = create_chama(client, headers)
        m = add_membership(client, headers, chama["id"], phone="+254700000460", govt="GID-460")
        client.post(
            f"/api/v1/chamas/{chama['id']}/memberships/{m['id']}/roles",
            headers=headers,
            json={"role": "SECRETARY"},
        )
        r = client.delete(
            f"/api/v1/chamas/{chama['id']}/memberships/{m['id']}/roles/SECRETARY",
            headers=headers,
        )
        assert r.status_code == 200
        assert "SECRETARY" not in r.json()["roles"]
        assert "MEMBER" in r.json()["roles"]

    def test_cannot_remove_member_role(self, client):
        headers = register_and_login(client, "chair@e.com")
        chama = create_chama(client, headers)
        m = add_membership(client, headers, chama["id"], phone="+254700000470", govt="GID-470")
        r = client.delete(
            f"/api/v1/chamas/{chama['id']}/memberships/{m['id']}/roles/MEMBER",
            headers=headers,
        )
        assert r.status_code == 400

    def test_non_chairperson_cannot_remove_role(self, client):
        headers = register_and_login(client, "chair@e.com")
        chama = create_chama(client, headers)
        m = add_membership(client, headers, chama["id"], phone="+254700000480", govt="GID-480")
        client.post(
            f"/api/v1/chamas/{chama['id']}/memberships/{m['id']}/roles",
            headers=headers,
            json={"role": "TREASURER"},
        )
        headers_member = register_and_login(client, "mem@e.com")
        r = client.delete(
            f"/api/v1/chamas/{chama['id']}/memberships/{m['id']}/roles/TREASURER",
            headers=headers_member,
        )
        assert r.status_code == 403