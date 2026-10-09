"""Canonical Kenyan phone normalization on member write/lookup (plan W4)."""

from tests.conftest import (
    add_membership,
    create_chama,
    register_and_login,
    register_unlinked_and_login,
)


class TestPhoneNormalization:
    def test_member_phone_stored_in_canonical_254_form(self, client):
        headers = register_unlinked_and_login(client, "chair@e.com")
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
        r = client.post(
            "/api/v1/auth/token",
            data={"username": "0722222222", "password": "GID-PN2"},
        )
        assert r.status_code == 200, r.json()
        assert r.json()["must_change_password"] is True

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
                    "email": "duplicate-phone@example.com",
                }
            },
        )
        assert r.status_code == 409
