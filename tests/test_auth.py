"""Authentication tests."""

import pytest

from tests.conftest import add_membership, create_chama, register_and_login


class TestRegister:
    def test_register_returns_user(self, client):
        r = client.post(
            "/api/v1/auth/register",
            json={"email": "alice@example.com", "password": "securepass123"},
        )
        assert r.status_code == 201
        body = r.json()
        assert body["email"] == "alice@example.com"
        assert "id" in body
        assert "password_hash" not in body

    def test_duplicate_email_rejected(self, client):
        client.post(
            "/api/v1/auth/register",
            json={"email": "dup@example.com", "password": "securepass123"},
        )
        r = client.post(
            "/api/v1/auth/register",
            json={"email": "dup@example.com", "password": "securepass456"},
        )
        assert r.status_code == 409


class TestToken:
    def test_login_returns_token(self, client):
        client.post(
            "/api/v1/auth/register",
            json={"email": "bob@example.com", "password": "securepass123"},
        )
        r = client.post(
            "/api/v1/auth/token",
            data={"username": "bob@example.com", "password": "securepass123"},
        )
        assert r.status_code == 200
        assert "access_token" in r.json()
        assert r.json()["token_type"] == "bearer"

    def test_wrong_password_rejected(self, client):
        client.post(
            "/api/v1/auth/register",
            json={"email": "carol@example.com", "password": "securepass123"},
        )
        r = client.post(
            "/api/v1/auth/token",
            data={"username": "carol@example.com", "password": "wrongpassword"},
        )
        assert r.status_code == 401

    def test_unknown_email_rejected(self, client):
        r = client.post(
            "/api/v1/auth/token",
            data={"username": "unknown@example.com", "password": "securepass123"},
        )
        assert r.status_code == 401


class TestMe:
    def test_me_returns_current_user(self, client):
        client.post(
            "/api/v1/auth/register",
            json={"email": "me@example.com", "password": "securepass123"},
        )
        r = client.post(
            "/api/v1/auth/token",
            data={"username": "me@example.com", "password": "securepass123"},
        )
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = client.get("/api/v1/auth/me", headers=headers)
        assert r.status_code == 200
        assert r.json()["email"] == "me@example.com"

    def test_me_requires_token(self, client):
        r = client.get("/api/v1/auth/me")
        assert r.status_code == 401

    def test_invalid_token_rejected(self, client):
        r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid"})
        assert r.status_code == 401


class TestMemberLink:
    def test_link_claims_member_identity(self, client):
        chair = register_and_login(client, "chair@example.com")
        chama = create_chama(client, chair)
        add_membership(client, chair, chama["id"], phone="+254700000771", govt="GID-771")
        headers = register_and_login(client, "member@example.com")
        r = client.post(
            "/api/v1/auth/me/member-link",
            headers=headers,
            json={"phone_number": "+254700000771", "government_id": "GID-771"},
        )
        assert r.status_code == 200
        assert r.json()["member_id"]

    def test_link_rejects_wrong_government_id(self, client):
        chair = register_and_login(client, "chair2@example.com")
        chama = create_chama(client, chair)
        add_membership(client, chair, chama["id"], phone="+254700000772", govt="GID-772")
        headers = register_and_login(client, "member2@example.com")
        r = client.post(
            "/api/v1/auth/me/member-link",
            headers=headers,
            json={"phone_number": "+254700000772", "government_id": "WRONG"},
        )
        assert r.status_code == 404

    def test_link_rejects_already_linked_account(self, client):
        headers = register_and_login(client, "creator@example.com")
        create_chama(client, headers)  # creator auto-links to their member
        r = client.post(
            "/api/v1/auth/me/member-link",
            headers=headers,
            json={"phone_number": "+254700000001", "government_id": "GID-001"},
        )
        assert r.status_code == 409

    def test_link_requires_auth(self, client):
        r = client.post(
            "/api/v1/auth/me/member-link",
            json={"phone_number": "+254700000001", "government_id": "GID-001"},
        )
        assert r.status_code == 401