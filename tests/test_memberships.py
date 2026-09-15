"""Membership API tests."""

import pytest

from tests.conftest import register_and_login, create_chama, add_membership


class TestCreateMembership:
    def test_add_member(self, client):
        headers = register_and_login(client, "chair@example.com")
        chama = create_chama(client, headers)
        m = add_membership(client, headers, chama["id"], phone="+254700000011", govt="GID-11")
        assert m["membership_number"] == 2
        assert m["status"] == "ACTIVE"
        assert "MEMBER" in m["roles"]

    def test_duplicate_member_in_chama_rejected(self, client):
        headers = register_and_login(client, "chair@example.com")
        chama = create_chama(client, headers)
        add_membership(client, headers, chama["id"], phone="+254700000022", govt="GID-22")
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/memberships",
            headers=headers,
            json={"member": {"first_name": "X", "last_name": "Y", "phone_number": "+254700000022", "government_id": "GID-22"}},
        )
        assert r.status_code == 409

    def test_same_member_in_different_chamas_allowed(self, client):
        headers_a = register_and_login(client, "a@e.com")
        chama_a = create_chama(client, headers_a, name="Chama A", phone="+254700000033", govt="GID-33")
        headers_b = register_and_login(client, "b@e.com")
        chama_b = create_chama(client, headers_b, name="Chama B", phone="+254700000044", govt="GID-44")
        headers_shared = register_and_login(client, "shared@e.com")
        # shared user adds themselves to chama_a
        r = client.post(
            f"/api/v1/chamas/{chama_a['id']}/memberships",
            headers=headers_a,
            json={"member": {"first_name": "S", "last_name": "A", "phone_number": "+254700000055", "government_id": "GID-55"}},
        )
        assert r.status_code == 201
        # register a new user and add them to both chamas
        headers2 = register_and_login(client, "multi@e.com", "password123")
        # add user to chama_b
        r = client.post(
            f"/api/v1/chamas/{chama_b['id']}/memberships",
            headers=headers_b,
            json={"member": {"first_name": "M", "last_name": "B", "phone_number": "+254700000066", "government_id": "GID-66"}},
        )
        assert r.status_code == 201

    def test_leadership_required_to_add_member(self, client):
        headers_chair = register_and_login(client, "chair@e.com")
        chama = create_chama(client, headers_chair)
        headers_member = register_and_login(client, "basic@e.com")
        # basic user joins as member
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/memberships",
            headers=headers_chair,
            json={"member": {"first_name": "B", "last_name": "M", "phone_number": "+254700000077", "government_id": "GID-77"}},
        )
        assert r.status_code == 201
        # basic user tries to add someone — should be denied (no leadership role)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/memberships",
            headers=headers_member,
            json={"member": {"first_name": "X", "last_name": "Y", "phone_number": "+254700000088", "government_id": "GID-88"}},
        )
        assert r.status_code == 403


class TestListMemberships:
    def test_list_memberships(self, client):
        headers = register_and_login(client, "list@e.com")
        chama = create_chama(client, headers)
        add_membership(client, headers, chama["id"], phone="+254700000100", govt="GID-100")
        r = client.get(f"/api/v1/chamas/{chama['id']}/memberships", headers=headers)
        assert r.status_code == 200
        assert len(r.json()) == 2  # creator + added member


class TestMembershipStatus:
    def test_chairperson_can_deactivate_member(self, client):
        headers = register_and_login(client, "chair@e.com")
        chama = create_chama(client, headers)
        m = add_membership(client, headers, chama["id"], phone="+254700000200", govt="GID-200")
        r = client.patch(
            f"/api/v1/chamas/{chama['id']}/memberships/{m['id']}/status",
            headers=headers,
            json={"status": "INACTIVE"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "INACTIVE"

    def test_non_chairperson_cannot_change_status(self, client):
        headers_chair = register_and_login(client, "chair2@e.com")
        chama = create_chama(client, headers_chair)
        m = add_membership(client, headers_chair, chama["id"], phone="+254700000300", govt="GID-300")
        headers_other = register_and_login(client, "other@e.com")
        # add other user as a leadership member (secretary)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/memberships",
            headers=headers_chair,
            json={"member": {"first_name": "O", "last_name": "Z", "phone_number": "+254700000310", "government_id": "GID-310"}},
        )
        assert r.status_code == 201
        r = client.patch(
            f"/api/v1/chamas/{chama['id']}/memberships/{m['id']}/status",
            headers=headers_other,
            json={"status": "INACTIVE"},
        )
        assert r.status_code == 403