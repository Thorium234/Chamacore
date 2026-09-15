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

    def test_create_chama_without_member_details_rejected(self, client):
        headers = register_and_login(client)
        r = client.post("/api/v1/chamas", headers=headers, json={"name": "No Member"})
        assert r.status_code == 400

    def test_unauthenticated_rejected(self, client):
        r = client.post("/api/v1/chamas", json={"name": "No Auth"})
        assert r.status_code == 401


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