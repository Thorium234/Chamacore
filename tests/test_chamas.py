"""Chama API tests."""

import pytest

from tests.conftest import register_and_login, create_chama


class TestCreateChama:
    def test_create_chama(self, client):
        headers = register_and_login(client, "creator@example.com")
        chama = create_chama(client, headers)
        assert chama["name"] == "Test Chama"
        assert chama["status"] == "ACTIVE"
        assert chama["registration_fee_amount"] == "100.00"

    def test_create_chama_response_has_membership(self, client):
        headers = register_and_login(client, "creator@example.com")
        chama = create_chama(client, headers)
        assert chama["membership_id"]
        assert set(chama["roles"]) == {"CHAIRPERSON", "MEMBER"}

    def test_create_chama_without_member_details_rejected(self, client):
        headers = register_and_login(client)
        r = client.post("/api/v1/chamas", headers=headers, json={"name": "No Member"})
        assert r.status_code == 400

    def test_unauthenticated_rejected(self, client):
        r = client.post("/api/v1/chamas", json={"name": "No Auth"})
        assert r.status_code == 401


class TestCreateChamaForLinkedUser:
    """A user already linked to a member keeps using that member (ADR-008)."""

    def _first_chama(self, client, headers):
        return create_chama(client, headers)

    def test_second_chama_reattaches_linked_member(self, client):
        headers = register_and_login(client, "linked@example.com")
        first = self._first_chama(client, headers)
        me = client.get("/api/v1/auth/me", headers=headers).json()
        assert me["member_id"] is not None

        r = client.post(
            "/api/v1/chamas",
            headers=headers,
            json={
                "name": "Second Chama",
                "registration_fee_amount": "200.00",
                "member": {
                    "first_name": "Different",
                    "last_name": "Identity",
                    "phone_number": "+254700000777",
                    "government_id": "GID-777",
                },
            },
        )
        assert r.status_code == 201, r.json()
        second = r.json()
        assert second["id"] != first["id"]

        me_after = client.get("/api/v1/auth/me", headers=headers).json()
        assert me_after["member_id"] == me["member_id"]

    def test_creator_can_access_new_chama_immediately(self, client):
        headers = register_and_login(client, "linked2@example.com")
        self._first_chama(client, headers)
        r = client.post(
            "/api/v1/chamas",
            headers=headers,
            json={"name": "Second Chama", "member": None},
        )
        assert r.status_code == 201, r.json()
        second_id = r.json()["id"]

        g = client.get(f"/api/v1/chamas/{second_id}", headers=headers)
        assert g.status_code == 200, g.json()

        memberships = client.get(
            f"/api/v1/chamas/{second_id}/memberships", headers=headers
        ).json()
        assert len(memberships) == 1
        me = client.get("/api/v1/auth/me", headers=headers).json()
        assert memberships[0]["member_id"] == me["member_id"]
        assert set(memberships[0]["roles"]) == {"CHAIRPERSON", "MEMBER"}

    def test_mismatched_identity_payload_is_ignored(self, client):
        headers = register_and_login(client, "linked3@example.com")
        self._first_chama(client, headers)
        me = client.get("/api/v1/auth/me", headers=headers).json()
        r = client.post(
            "/api/v1/chamas",
            headers=headers,
            json={
                "name": "Second Chama",
                "member": {
                    "first_name": "Bogus",
                    "last_name": "Identity",
                    "phone_number": "+254700000888",
                    "government_id": "GID-888",
                },
            },
        )
        assert r.status_code == 201, r.json()
        memberships = client.get(
            f"/api/v1/chamas/{r.json()['id']}/memberships", headers=headers
        ).json()
        assert len(memberships) == 1
        assert memberships[0]["member_id"] == me["member_id"]


class TestListChamas:
    def test_lists_only_active_membership_chamas(self, client):
        headers = register_and_login(client, "multi@example.com")
        first = create_chama(client, headers)
        second = client.post(
            "/api/v1/chamas",
            headers=headers,
            json={"name": "Second Chama"},
        ).json()
        r = client.get("/api/v1/chamas", headers=headers)
        assert r.status_code == 200
        ids = {item["id"] for item in r.json()}
        assert ids == {first["id"], second["id"]}

    def test_unlinked_user_gets_empty_list(self, client):
        headers = register_and_login(client, "fresh@example.com")
        r = client.get("/api/v1/chamas", headers=headers)
        assert r.status_code == 200
        assert r.json() == []


class TestGetChama:
    def test_owner_can_get_chama(self, client):
        headers = register_and_login(client, "owner@example.com")
        chama = create_chama(client, headers)
        r = client.get(f"/api/v1/chamas/{chama['id']}", headers=headers)
        assert r.status_code == 200
        assert r.json()["id"] == chama["id"]

    def test_non_member_cannot_get_chama(self, client):
        headers_a = register_and_login(client, "a@example.com")
        chama = create_chama(client, headers_a)
        headers_b = register_and_login(client, "b@example.com")
        r = client.get(f"/api/v1/chamas/{chama['id']}", headers=headers_b)
        assert r.status_code == 403

    def test_nonexistent_chama_returns_404(self, client):
        import uuid

        headers = register_and_login(client)
        r = client.get(f"/api/v1/chamas/{uuid.uuid4()}", headers=headers)
        assert r.status_code == 404


class TestUpdateChama:
    def test_chairperson_can_update_name(self, client):
        headers = register_and_login(client, "chair@example.com")
        chama = create_chama(client, headers)
        r = client.patch(
            f"/api/v1/chamas/{chama['id']}",
            headers=headers,
            json={"name": "Updated Name"},
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Updated Name"

    def test_non_chairperson_cannot_update(self, client):
        headers = register_and_login(client, "chair@example.com")
        chama = create_chama(client, headers, phone="+254700000002", govt="GID-002")
        headers2 = register_and_login(client, "member@example.com")
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/memberships",
            headers=headers,
            json={"member": {"first_name": "M", "last_name": "N", "phone_number": "+254700000010", "government_id": "GID-10"}},
        )
        assert r.status_code == 201
        r = client.patch(
            f"/api/v1/chamas/{chama['id']}",
            headers=headers2,
            json={"name": "Hacked"},
        )
        assert r.status_code == 403

    def test_activate_deactivate_chama(self, client):
        headers = register_and_login(client, "status@example.com")
        chama = create_chama(client, headers)
        r = client.patch(
            f"/api/v1/chamas/{chama['id']}", headers=headers, json={"status": "INACTIVE"}
        )
        assert r.status_code == 200
        assert r.json()["status"] == "INACTIVE"
        r = client.patch(
            f"/api/v1/chamas/{chama['id']}", headers=headers, json={"status": "ACTIVE"}
        )
        assert r.json()["status"] == "ACTIVE"