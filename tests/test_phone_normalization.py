"""Canonical Kenyan phone normalization on member write/lookup (plan W4)."""

from tests.conftest import register_and_login, create_chama, add_membership


class TestPhoneNormalization:
    def test_member_phone_stored_in_canonical_254_form(self, client):
        headers = register_and_login(client, "chair@e.com")
        chama = create_chama(client, headers, phone="0712345678", govt="GID-PN1")
        memberships = client.get(
            f"/api/v1/chamas/{chama['id']}/memberships", headers=headers
        ).json()
        chair = next(x for x in memberships if x["id"] == chama["membership_id"])
        assert chair["member"]["phone_number"] == "254712345678"

    def test_member_link_accepts_non_canonical_phone(self, client):
        headers = register_and_login(client, "chair@e.com")
        chama = create_chama(client, headers)
        add_membership(client, headers, chama["id"], phone="0722222222", govt="GID-PN2")
        client.post("/api/v1/auth/register", json={"email": "bob@e.com", "password": "password123"})
        r = client.post("/api/v1/auth/token", data={"username": "bob@e.com", "password": "password123"})
        bob_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = client.post(
            "/api/v1/auth/me/member-link",
            headers=bob_headers,
            json={"phone_number": "0722222222", "government_id": "GID-PN2"},
        )
        assert r.status_code == 200

    def test_duplicate_canonical_phone_rejected(self, client):
        headers = register_and_login(client, "chair@e.com")
        chama = create_chama(client, headers)
        add_membership(client, headers, chama["id"], phone="0722333444", govt="GID-PN3")
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/memberships",
            headers=headers,
            json={
                "member": {
                    "first_name": "D",
                    "last_name": "U",
                    "phone_number": "+254722333444",
                    "government_id": "GID-PN4",
                }
            },
        )
        assert r.status_code == 409