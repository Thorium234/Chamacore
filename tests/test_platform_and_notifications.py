"""Platform administration, notification, and forced password-change tests."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select

from app.models.enums import MembershipStatus, RoleName
from app.models.membership import Membership
from app.models.notification import Notification
from app.models.user import User
from app.models.user_platform_role import UserPlatformRole
from tests.conftest import add_membership, create_chama, register_and_login


def _make_admin(client, db, email="admin@e.com") -> str:
    """Register a user and grant the global PLATFORM_ADMIN role directly."""
    register_and_login(client, email, password="StrongPassword1!")
    user = db.scalar(select(User).where(User.email == email))
    assert user is not None
    db.add(
        UserPlatformRole(
            user_id=user.id,
            role=RoleName.PLATFORM_ADMIN,
            granted_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    return str(user.id)


def _admin_headers(client, email="admin@e.com") -> dict:
    r = client.post(
        "/api/v1/auth/token",
        data={"username": email, "password": "StrongPassword1!"},
    )
    assert r.status_code == 200, r.json()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


class TestPlatformAuthorization:
    def test_non_admin_cannot_list_platform_chamas(self, client):
        headers = register_and_login(client, "chair@e.com")
        create_chama(client, headers, fee="0.00")
        r = client.get("/api/v1/platform/chamas", headers=headers)
        assert r.status_code == 403

    def test_anonymous_cannot_list_platform_chamas(self, client):
        assert client.get("/api/v1/platform/chamas").status_code == 401

    def test_admin_can_list_all_chamas(self, client, db):
        _make_admin(client, db)
        admin = _admin_headers(client)
        r = client.get("/api/v1/platform/chamas", headers=admin)
        assert r.status_code == 200, r.json()
        assert len(r.json()) == 0

    def test_admin_sees_chamas_they_are_not_a_member_of(self, client, db):
        headers = register_and_login(client, "chair@e.com")
        chama = create_chama(client, headers, name="Other Chama", fee="0.00")
        _make_admin(client, db)
        admin = _admin_headers(client)
        r = client.get("/api/v1/platform/chamas", headers=admin)
        assert r.status_code == 200
        assert [c["id"] for c in r.json()] == [chama["id"]]
        assert r.json()[0]["name"] == "Other Chama"

    def test_platform_admin_membership_is_not_a_chama_role(self, client, db):
        """A platform admin grant must not appear as a Chama membership role."""
        headers = register_and_login(client, "chair@e.com")
        chama = create_chama(client, headers, fee="0.00")
        _make_admin(client, db)
        r = client.get(f"/api/v1/chamas/{chama['id']}", headers=headers)
        assert r.status_code == 200
        assert "PLATFORM_ADMIN" not in str(r.json())


class TestPlatformChamaStatus:
    def _setup(self, client, db):
        chair = register_and_login(client, "chair@e.com")
        chama = create_chama(client, chair, name="Lifecycle Chama", fee="0.00")
        _make_admin(client, db)
        return chair, chama, _admin_headers(client)

    def test_admin_can_suspend_chama(self, client, db):
        _, chama, admin = self._setup(client, db)
        r = client.patch(
            f"/api/v1/platform/chamas/{chama['id']}/status",
            headers=admin,
            json={"status": "SUSPENDED", "reason": "under review"},
        )
        assert r.status_code == 200, r.json()
        assert r.json()["status"] == "SUSPENDED"

    def test_admin_can_reactivate_suspended_chama(self, client, db):
        _, chama, admin = self._setup(client, db)
        client.patch(
            f"/api/v1/platform/chamas/{chama['id']}/status",
            headers=admin,
            json={"status": "SUSPENDED"},
        )
        r = client.patch(
            f"/api/v1/platform/chamas/{chama['id']}/status",
            headers=admin,
            json={"status": "ACTIVE"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "ACTIVE"

    def test_dissolved_is_terminal(self, client, db):
        _, chama, admin = self._setup(client, db)
        r = client.patch(
            f"/api/v1/platform/chamas/{chama['id']}/status",
            headers=admin,
            json={"status": "DISSOLVED"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "DISSOLVED"
        again = client.patch(
            f"/api/v1/platform/chamas/{chama['id']}/status",
            headers=admin,
            json={"status": "ACTIVE"},
        )
        assert again.status_code == 400

    def test_cannot_activate_a_dissolved_chama_directly(self, client, db):
        _, chama, admin = self._setup(client, db)
        client.patch(
            f"/api/v1/platform/chamas/{chama['id']}/status",
            headers=admin,
            json={"status": "DISSOLVED"},
        )
        r = client.patch(
            f"/api/v1/platform/chamas/{chama['id']}/status",
            headers=admin,
            json={"status": "ACTIVE"},
        )
        assert r.status_code == 400
        assert "dissolved" in r.json()["detail"]["message"].lower()

    def test_non_admin_cannot_change_chama_status(self, client, db):
        chair, chama, _ = self._setup(client, db)
        r = client.patch(
            f"/api/v1/platform/chamas/{chama['id']}/status",
            headers=chair,
            json={"status": "SUSPENDED"},
        )
        assert r.status_code == 403

    def test_missing_chama_is_404(self, client, db):
        self._setup(client, db)
        admin = _admin_headers(client)
        r = client.patch(
            f"/api/v1/platform/chamas/{uuid.uuid4()}/status",
            headers=admin,
            json={"status": "SUSPENDED"},
        )
        assert r.status_code == 404

    def test_status_change_is_audited(self, client, db):
        from app.models.audit_event import AuditEvent

        _, chama, admin = self._setup(client, db)
        client.patch(
            f"/api/v1/platform/chamas/{chama['id']}/status",
            headers=admin,
            json={"status": "SUSPENDED", "reason": "audit check"},
        )
        events = db.scalars(
            select(AuditEvent).where(
                AuditEvent.action == "platform.chama_status_change"
            )
        ).all()
        assert len(events) == 1
        assert events[0].payload["from"] == "ACTIVE"
        assert events[0].payload["to"] == "SUSPENDED"
        assert events[0].payload["reason"] == "audit check"

    def test_repeated_same_status_is_a_noop(self, client, db):
        from app.models.audit_event import AuditEvent

        _, chama, admin = self._setup(client, db)
        r = client.patch(
            f"/api/v1/platform/chamas/{chama['id']}/status",
            headers=admin,
            json={"status": "ACTIVE"},
        )
        assert r.status_code == 200
        assert (
            db.scalar(
                select(AuditEvent).where(
                    AuditEvent.action == "platform.chama_status_change"
                )
            )
            is None
        )


class TestPlatformAdminGrants:
    def test_grant_and_revoke(self, client, db):
        _make_admin(client, db)
        admin = _admin_headers(client)
        client.post("/api/v1/auth/register", json={"email": "user@e.com", "password": "OldPassword123!"})
        target = db.scalar(select(User).where(User.email == "user@e.com"))
        r = client.post(
            "/api/v1/platform/admins",
            headers=admin,
            json={"email": "user@e.com"},
        )
        assert r.status_code == 201, r.json()
        assert r.json()["platform_roles"] == ["PLATFORM_ADMIN"]
        assert db.scalar(
            select(UserPlatformRole).where(UserPlatformRole.user_id == target.id)
        ) is not None
        d = client.delete(
            f"/api/v1/platform/admins/{target.id}",
            headers=admin,
        )
        assert d.status_code == 200
        assert db.scalar(
            select(UserPlatformRole).where(UserPlatformRole.user_id == target.id)
        ) is None

    def test_granting_twice_conflicts(self, client, db):
        _make_admin(client, db)
        admin = _admin_headers(client)
        client.post("/api/v1/auth/register", json={"email": "user@e.com", "password": "OldPassword123!"})
        target = db.scalar(select(User).where(User.email == "user@e.com"))
        client.post(
            "/api/v1/platform/admins", headers=admin, json={"email": "user@e.com"}
        )
        again = client.post(
            "/api/v1/platform/admins", headers=admin, json={"email": "user@e.com"}
        )
        assert again.status_code == 409

    def test_cannot_revoke_own_grant(self, client, db):
        admin_id = _make_admin(client, db)
        admin = _admin_headers(client)
        r = client.delete(
            f"/api/v1/platform/admins/{admin_id}", headers=admin
        )
        assert r.status_code == 400

    def test_last_admin_cannot_be_revoked(self, client, db):
        admin_id = _make_admin(client, db)
        admin = _admin_headers(client)
        client.post("/api/v1/auth/register", json={"email": "user@e.com", "password": "OldPassword123!"})
        target = db.scalar(select(User).where(User.email == "user@e.com"))
        client.post(
            "/api/v1/platform/admins", headers=admin, json={"email": "user@e.com"}
        )
        # revoke the other admin first: allowed, two admins exist
        r = client.delete(
            f"/api/v1/platform/admins/{target.id}", headers=admin
        )
        assert r.status_code == 200
        # now the caller is the only admin and cannot revoke themselves
        self_only = client.delete(
            f"/api/v1/platform/admins/{admin_id}", headers=admin
        )
        assert self_only.status_code == 400

    def test_non_admin_cannot_grant(self, client, db):
        headers = register_and_login(client, "chair@e.com")
        r = client.post(
            "/api/v1/platform/admins",
            headers=headers,
            json={"email": "nobody@example.com"},
        )
        assert r.status_code == 403

    def test_platform_admin_is_not_a_chama_role(self, client, db):
        """PLATFORM_ADMIN must not be assignable or listable inside a Chama."""
        headers = register_and_login(client, "chair@e.com")
        chama = create_chama(client, headers, name="Role Chama", fee="0.00")
        member = add_membership(
            client, headers, chama["id"], phone="+254700000444", govt="GID-444"
        )
        listed = client.get(f"/api/v1/chamas/{chama['id']}/roles", headers=headers)
        assert listed.status_code == 200
        assert "PLATFORM_ADMIN" not in [r["name"] for r in listed.json()]
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/memberships/{member['id']}/roles",
            headers=headers,
            json={"role": "PLATFORM_ADMIN"},
        )
        assert r.status_code == 400

    def test_only_platform_admin_role_is_grantable(self, client, db):
        _make_admin(client, db)
        admin = _admin_headers(client)
        client.post("/api/v1/auth/register", json={"email": "user@e.com", "password": "OldPassword123!"})
        target = db.scalar(select(User).where(User.email == "user@e.com"))
        r = client.post(
            "/api/v1/platform/admins",
            headers=admin,
            json={"email": "user@e.com", "role": "TREASURER"},
        )
        assert r.status_code == 422

    def test_revoke_unassigned_is_404(self, client, db):
        _make_admin(client, db)
        admin = _admin_headers(client)
        client.post("/api/v1/auth/register", json={"email": "user@e.com", "password": "OldPassword123!"})
        target = db.scalar(select(User).where(User.email == "user@e.com"))
        r = client.delete(
            f"/api/v1/platform/admins/{target.id}", headers=admin
        )
        assert r.status_code == 404


class TestPlatformStats:
    def test_stats_requires_admin(self, client):
        headers = register_and_login(client, "chair@e.com")
        assert client.get("/api/v1/platform/stats", headers=headers).status_code == 403

    def test_counts_chamas_and_users(self, client, db):
        headers = register_and_login(client, "chair@e.com")
        create_chama(client, headers, name="Stats Chama", fee="0.00", activate=False)
        _make_admin(client, db)
        admin = _admin_headers(client)
        r = client.get("/api/v1/platform/stats", headers=admin)
        assert r.status_code == 200, r.json()
        body = r.json()
        assert body["total_chamas"] == 1
        assert body["pending_chamas"] == 1
        assert body["platform_admins"] == 1
        assert body["total_users"] >= 2
        assert body["total_members"] >= 1


class TestPlatformUserOperations:
    def test_admin_can_search_by_phone_and_force_password_change(self, client, db):
        _make_admin(client, db)
        admin = _admin_headers(client)
        target_headers = register_and_login(client, "lookup@e.com")
        target = db.scalar(select(User).where(User.email == "lookup@e.com"))
        assert target is not None and target.member is not None

        found = client.get(
            f"/api/v1/platform/users?search={target.member.phone_number}",
            headers=admin,
        )
        assert found.status_code == 200, found.json()
        assert [item["id"] for item in found.json()] == [str(target.id)]
        assert "government_id" not in found.json()[0]

        forced = client.post(
            f"/api/v1/platform/users/{target.id}/require-password-change",
            headers=admin,
        )
        assert forced.status_code == 200, forced.json()
        assert forced.json()["must_change_password"] is True
        assert client.get("/api/v1/auth/me", headers=target_headers).status_code == 200

    def test_admin_can_deactivate_and_reactivate_login(self, client, db):
        _make_admin(client, db)
        admin = _admin_headers(client)
        target_headers = register_and_login(client, "lock@e.com")
        target = db.scalar(select(User).where(User.email == "lock@e.com"))
        assert target is not None

        locked = client.post(
            f"/api/v1/platform/users/{target.id}/deactivate", headers=admin
        )
        assert locked.status_code == 200, locked.json()
        assert locked.json()["is_active"] is False
        assert client.get("/api/v1/auth/me", headers=target_headers).status_code == 401

        unlocked = client.post(
            f"/api/v1/platform/users/{target.id}/reactivate", headers=admin
        )
        assert unlocked.status_code == 200, unlocked.json()
        assert unlocked.json()["is_active"] is True


class TestPlatformChamaFilters:
    def test_filter_by_status_and_counts(self, client, db):
        headers = register_and_login(client, "chair@e.com")
        active = create_chama(client, headers, name="Alpha", fee="0.00")
        second = create_chama(client, headers, name="Beta", fee="0.00")
        add_membership(client, headers, second["id"], phone="+254700000777", govt="GID-777")
        _make_admin(client, db)
        admin = _admin_headers(client)
        client.patch(
            f"/api/v1/platform/chamas/{active['id']}/status",
            headers=admin,
            json={"status": "SUSPENDED"},
        )
        listed = client.get("/api/v1/platform/chamas?status=SUSPENDED", headers=admin)
        assert [c["id"] for c in listed.json()] == [active["id"]]
        suspended = listed.json()[0]
        assert suspended["membership_count"] == 1
        assert suspended["active_member_count"] == 1
        searched = client.get("/api/v1/platform/chamas?search=Beta", headers=admin)
        assert [c["id"] for c in searched.json()] == [second["id"]]

    def test_platform_view_counts_inactive_members_separately(self, client, db):
        headers = register_and_login(client, "chair@e.com")
        chama = create_chama(client, headers, fee="0.00")
        member = add_membership(
            client, headers, chama["id"], phone="+254700000888", govt="GID-888"
        )
        _make_admin(client, db)
        admin = _admin_headers(client)
        row = db.get(Membership, uuid.UUID(member["id"]))
        row.status = MembershipStatus.INACTIVE
        db.commit()
        r = client.get(f"/api/v1/platform/chamas/{chama['id']}", headers=admin)
        assert r.status_code == 200
        assert r.json()["membership_count"] == 2
        assert r.json()["active_member_count"] == 1


class TestMustChangePassword:
    def test_login_reports_must_change_password(self, client, db):
        _make_admin(client, db)
        admin = _admin_headers(client)
        client.post("/api/v1/auth/register", json={"email": "user@e.com", "password": "OldPassword123!"})
        target = db.scalar(select(User).where(User.email == "user@e.com"))
        r = client.post(
            f"/api/v1/platform/users/{target.id}/require-password-change",
            headers=admin,
            json=None,
        )
        assert r.status_code == 200, r.json()
        assert r.json()["must_change_password"] is True
        login = client.post(
            "/api/v1/auth/token", data={"username": "user@e.com", "password": "OldPassword123!"}
        )
        assert login.status_code == 200
        assert login.json()["must_change_password"] is True

    def test_default_login_flag_is_false(self, client):
        client.post("/api/v1/auth/register", json={"email": "user@e.com", "password": "OldPassword123!"})
        login = client.post(
            "/api/v1/auth/token", data={"username": "user@e.com", "password": "OldPassword123!"}
        )
        assert login.json()["must_change_password"] is False

    def test_change_password_clears_flag_and_revokes_refresh(self, client, db):
        _make_admin(client, db)
        admin = _admin_headers(client)
        client.post("/api/v1/auth/register", json={"email": "user@e.com", "password": "OldPassword123!"})
        target = db.scalar(select(User).where(User.email == "user@e.com"))
        client.post(
            f"/api/v1/platform/users/{target.id}/require-password-change", headers=admin
        )
        login = client.post(
            "/api/v1/auth/token", data={"username": "user@e.com", "password": "OldPassword123!"}
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        stale_refresh = login.json()["refresh_token"]
        r = client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={"current_password": "OldPassword123!", "new_password": "NewPassword456!"},
        )
        assert r.status_code == 200, r.json()
        assert r.json()["must_change_password"] is False
        # the pre-change refresh token no longer works
        stale = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": stale_refresh}
        )
        assert stale.status_code == 401
        # the new password works and the flag is cleared
        again = client.post(
            "/api/v1/auth/token", data={"username": "user@e.com", "password": "NewPassword456!"}
        )
        assert again.status_code == 200
        assert again.json()["must_change_password"] is False

    def test_wrong_current_password_rejected(self, client):
        headers = register_and_login(client, "user@e.com")
        r = client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={"current_password": "wrongpass", "new_password": "NewPassword456!"},
        )
        assert r.status_code == 400

    def test_same_password_rejected(self, client):
        password = "StrongTestPassword123!"
        headers = register_and_login(client, "user@e.com", password=password)
        r = client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={"current_password": password, "new_password": password},
        )
        assert r.status_code == 400
        assert "different" in r.json()["detail"].lower()

    def test_short_new_password_rejected(self, client):
        password = "StrongTestPassword123!"
        headers = register_and_login(client, "user@e.com", password=password)
        r = client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={"current_password": password, "new_password": "short"},
        )
        assert r.status_code == 422

    def test_change_password_requires_auth(self, client):
        r = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "OldPassword123!", "new_password": "NewPassword456!"},
        )
        assert r.status_code == 401

    def test_refresh_preserves_must_change_flag(self, client, db):
        _make_admin(client, db)
        admin = _admin_headers(client)
        client.post("/api/v1/auth/register", json={"email": "user@e.com", "password": "OldPassword123!"})
        target = db.scalar(select(User).where(User.email == "user@e.com"))
        client.post(
            f"/api/v1/platform/users/{target.id}/require-password-change", headers=admin
        )
        login = client.post(
            "/api/v1/auth/token", data={"username": "user@e.com", "password": "OldPassword123!"}
        ).json()
        refreshed = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]}
        )
        assert refreshed.status_code == 200
        assert refreshed.json()["must_change_password"] is True

    def test_non_admin_cannot_force_password_change(self, client, db):
        headers = register_and_login(client, "chair@e.com")
        client.post("/api/v1/auth/register", json={"email": "user@e.com", "password": "OldPassword123!"})
        target = db.scalar(select(User).where(User.email == "user@e.com"))
        r = client.post(
            f"/api/v1/platform/users/{target.id}/require-password-change", headers=headers
        )
        assert r.status_code == 403


class TestNotifications:
    def _chair_with_member(self, client, db):
        headers = register_and_login(client, "chair@e.com")
        chama = create_chama(client, headers, name="Notify Chama", fee="0.00")
        member = add_membership(
            client,
            headers,
            chama["id"],
            phone="+254700000321",
            govt="GID-321",
            email="member@e.com",
        )
        # The fixture needs an existing member account; discard its welcome
        # notification so each test can assert only the action it triggers.
        db.execute(
            delete(Notification).where(
                Notification.chama_id == uuid.UUID(chama["id"])
            )
        )
        db.commit()
        return headers, chama, member

    def _member_headers(self, client, phone="+254700000321", govt="GID-321", email="member@e.com"):
        r = client.post("/api/v1/auth/token", data={"username": phone, "password": govt})
        assert r.status_code == 200, r.json()
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
        changed = client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={"current_password": govt, "new_password": "MemberChangedPass123!"},
        )
        assert changed.status_code == 200, changed.json()
        return headers

    def test_list_requires_auth(self, client):
        assert client.get("/api/v1/notifications").status_code == 401

    def test_empty_feed_for_new_user(self, client):
        headers = register_and_login(client, "user@e.com")
        r = client.get("/api/v1/notifications", headers=headers)
        assert r.status_code == 200
        assert r.json() == []

    def test_contribution_record_notifies_the_member(self, client, db):
        headers, chama, member = self._chair_with_member(client, db)
        member_headers = self._member_headers(client)
        r = client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": member["id"], "amount": "1000.00", "period": "2026-09"},
        )
        assert r.status_code == 201, r.json()
        feed = client.get("/api/v1/notifications", headers=member_headers).json()
        assert [n["action"] for n in feed] == ["contribution.create"]
        assert feed[0]["chama_id"] == chama["id"]
        assert feed[0]["is_read"] is False

    def test_actor_does_not_notify_self(self, client, db):
        headers, chama, member = self._chair_with_member(client, db)
        client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": member["id"], "amount": "1000.00", "period": "2026-09"},
        )
        feed = client.get("/api/v1/notifications", headers=headers).json()
        assert feed == []

    def test_membership_create_notifies_everyone_but_the_actor(self, client, db):
        headers, chama, _ = self._chair_with_member(client, db)
        member_headers = self._member_headers(client)
        add_membership(
            client, headers, chama["id"], phone="+254700000322", govt="GID-322"
        )
        feed = client.get("/api/v1/notifications", headers=member_headers).json()
        assert [n["action"] for n in feed] == ["membership.create"]
        assert feed[0]["title"] == "New membership registered"

    def test_membership_status_change_notifies_the_affected_member(self, client, db):
        headers, chama, member = self._chair_with_member(client, db)
        member_headers = self._member_headers(client)
        r = client.patch(
            f"/api/v1/chamas/{chama['id']}/memberships/{member['id']}/status",
            headers=headers,
            json={"status": "INACTIVE"},
        )
        assert r.status_code == 200, r.json()
        feed = client.get("/api/v1/notifications", headers=member_headers).json()
        assert [n["action"] for n in feed] == ["membership.status_change"]
        assert feed[0]["payload"]["to"] == "INACTIVE"

    def test_chama_status_change_notifies_other_platform_admins(self, client, db):
        headers, chama, _ = self._chair_with_member(client, db)
        _make_admin(client, db, email="admin1@e.com")
        admin1 = _admin_headers(client, email="admin1@e.com")
        _make_admin(client, db, email="admin2@e.com")
        admin2 = _admin_headers(client, email="admin2@e.com")
        client.patch(
            f"/api/v1/platform/chamas/{chama['id']}/status",
            headers=admin1,
            json={"status": "SUSPENDED"},
        )
        # The acting admin is not notified of their own action.
        assert client.get("/api/v1/notifications", headers=admin1).json() == []
        feed = client.get("/api/v1/notifications", headers=admin2).json()
        assert [n["action"] for n in feed] == ["platform.chama_status_change"]
        assert feed[0]["chama_id"] == chama["id"]

    def test_notifications_are_scoped_per_user(self, client, db):
        headers, chama, member = self._chair_with_member(client, db)
        first = self._member_headers(client)
        client.post("/api/v1/auth/register", json={"email": "m2@e.com", "password": "OldPassword123!"})
        r = client.post(
            "/api/v1/auth/token", data={"username": "m2@e.com", "password": "OldPassword123!"}
        )
        second = {"Authorization": f"Bearer {r.json()['access_token']}"}
        client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": member["id"], "amount": "1000.00", "period": "2026-09"},
        )
        assert len(client.get("/api/v1/notifications", headers=first).json()) == 1
        assert client.get("/api/v1/notifications", headers=second).json() == []

    def test_mark_read_and_unread_count(self, client, db):
        headers, chama, member = self._chair_with_member(client, db)
        member_headers = self._member_headers(client)
        client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": member["id"], "amount": "1000.00", "period": "2026-09"},
        )
        count = client.get("/api/v1/notifications/unread-count", headers=member_headers)
        assert count.json()["unread_count"] == 1
        notif_id = client.get("/api/v1/notifications", headers=member_headers).json()[0]["id"]
        marked = client.post(
            f"/api/v1/notifications/{notif_id}/read", headers=member_headers
        )
        assert marked.status_code == 200
        assert marked.json()["is_read"] is True
        assert marked.json()["read_at"] is not None
        assert client.get(
            "/api/v1/notifications/unread-count", headers=member_headers
        ).json()["unread_count"] == 0

    def test_mark_read_is_idempotent(self, client, db):
        headers, chama, member = self._chair_with_member(client, db)
        member_headers = self._member_headers(client)
        client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": member["id"], "amount": "1000.00", "period": "2026-09"},
        )
        notif_id = client.get("/api/v1/notifications", headers=member_headers).json()[0]["id"]
        first = client.post(f"/api/v1/notifications/{notif_id}/read", headers=member_headers)
        second = client.post(f"/api/v1/notifications/{notif_id}/read", headers=member_headers)
        assert first.status_code == 200 and second.status_code == 200
        assert first.json()["is_read"] is True
        assert second.json()["is_read"] is True
        # The original read timestamp is preserved, not re-stamped. SQLite
        # returns naive timestamps, so compare them as UTC.
        def _utc(value: str) -> datetime:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

        assert _utc(second.json()["read_at"]) == _utc(first.json()["read_at"])

    def test_cannot_read_another_users_notification(self, client, db):
        headers, chama, member = self._chair_with_member(client, db)
        member_headers = self._member_headers(client)
        client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": member["id"], "amount": "1000.00", "period": "2026-09"},
        )
        notif_id = client.get("/api/v1/notifications", headers=member_headers).json()[0]["id"]
        r = client.post(f"/api/v1/notifications/{notif_id}/read", headers=headers)
        assert r.status_code == 404
        assert db.get(Notification, uuid.UUID(notif_id)).is_read is False

    def test_read_all(self, client, db):
        headers, chama, member = self._chair_with_member(client, db)
        member_headers = self._member_headers(client)
        for period in ("2026-01", "2026-02", "2026-03"):
            client.post(
                f"/api/v1/chamas/{chama['id']}/contributions",
                headers=headers,
                json={
                    "membership_id": member["id"],
                    "amount": "1000.00",
                    "period": period,
                },
            )
        assert client.get(
            "/api/v1/notifications/unread-count", headers=member_headers
        ).json()["unread_count"] == 3
        r = client.post("/api/v1/notifications/read-all", headers=member_headers)
        assert r.status_code == 200
        assert r.json()["updated"] == 3
        assert client.get(
            "/api/v1/notifications/unread-count", headers=member_headers
        ).json()["unread_count"] == 0

    def test_unread_only_filter(self, client, db):
        headers, chama, member = self._chair_with_member(client, db)
        member_headers = self._member_headers(client)
        for period in ("2026-01", "2026-02"):
            client.post(
                f"/api/v1/chamas/{chama['id']}/contributions",
                headers=headers,
                json={
                    "membership_id": member["id"],
                    "amount": "1000.00",
                    "period": period,
                },
            )
        all_rows = client.get("/api/v1/notifications", headers=member_headers).json()
        client.post(f"/api/v1/notifications/{all_rows[0]['id']}/read", headers=member_headers)
        unread = client.get(
            "/api/v1/notifications?unread_only=true", headers=member_headers
        ).json()
        assert len(unread) == 1
        assert unread[0]["id"] != all_rows[0]["id"]

    def test_delete_notification(self, client, db):
        headers, chama, member = self._chair_with_member(client, db)
        member_headers = self._member_headers(client)
        client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": member["id"], "amount": "1000.00", "period": "2026-09"},
        )
        notif_id = client.get("/api/v1/notifications", headers=member_headers).json()[0]["id"]
        r = client.delete(f"/api/v1/notifications/{notif_id}", headers=member_headers)
        assert r.status_code == 204
        assert client.get("/api/v1/notifications", headers=member_headers).json() == []

    def test_notification_rows_are_scoped_by_chama(self, client, db):
        headers, chama, member = self._chair_with_member(client, db)
        member_headers = self._member_headers(client)
        client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": member["id"], "amount": "1000.00", "period": "2026-09"},
        )
        other = create_chama(client, headers, name="Second", fee="0.00")
        r = client.get(
            f"/api/v1/notifications?chama_id={other['id']}", headers=member_headers
        )
        assert r.json() == []

    def test_pagination(self, client, db):
        headers, chama, member = self._chair_with_member(client, db)
        member_headers = self._member_headers(client)
        for period in ("2026-01", "2026-02", "2026-03"):
            client.post(
                f"/api/v1/chamas/{chama['id']}/contributions",
                headers=headers,
                json={
                    "membership_id": member["id"],
                    "amount": "1000.00",
                    "period": period,
                },
            )
        page = client.get("/api/v1/notifications?limit=2", headers=member_headers).json()
        assert len(page) == 2
        second = client.get(
            "/api/v1/notifications?limit=2&offset=2", headers=member_headers
        ).json()
        assert len(second) == 1
        assert page[0]["id"] != second[0]["id"]

    def test_login_events_do_not_create_notifications(self, client):
        headers = register_and_login(client, "user@e.com")
        assert client.get("/api/v1/notifications", headers=headers).json() == []

    def test_audit_events_are_unaffected(self, client, db):
        """Notification fan-out must not disturb the append-only audit trail."""
        from app.models.audit_event import AuditEvent

        headers, chama, member = self._chair_with_member(client, db)
        client.post(
            f"/api/v1/chamas/{chama['id']}/contributions",
            headers=headers,
            json={"membership_id": member["id"], "amount": "1000.00", "period": "2026-09"},
        )
        events = db.scalars(
            select(AuditEvent).where(AuditEvent.action == "contribution.create")
        ).all()
        assert len(events) == 1
        notification = db.scalar(
            select(Notification).where(Notification.action == "contribution.create")
        )
        assert notification is not None
