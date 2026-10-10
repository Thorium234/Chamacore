"""Refresh-token flow, short access TTL, and system-account login guard.

Coverage for the production-readiness brief 3.1:
- access tokens are short-lived by default
- refresh tokens are single-use and rotate on use
- logout revokes the presented refresh token
- the system posting account can never obtain a JWT
- an expired access token is rejected rather than accepted
"""

from datetime import datetime, timedelta, timezone

import jwt as pyjwt
from sqlalchemy import select

from app.core.config import get_settings
from app.models.user import User


def _register_and_login(client, db, email="refresh@example.com", password="StrongPassword123!"):
    r = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201
    r = client.post("/api/v1/auth/token", data={"username": email, "password": password})
    assert r.status_code == 200
    body = r.json()
    user = db.scalars(select(User).where(User.email == email)).one()
    return {"Authorization": f"Bearer {body['access_token']}"}, body, user


def test_login_returns_refresh_token_and_short_expiry(client, db):
    _, body, _ = _register_and_login(client, db)
    assert body["token_type"] == "bearer"
    assert body["refresh_token"]
    # Default access-token lifetime dropped to 120 minutes (brief 3.1).
    assert get_settings().jwt_expires_minutes == 120
    assert body["expires_in"] == 120 * 60


def test_refresh_rotates_and_revokes_previous_token(client, db):
    headers, body, user = _register_and_login(client, db)
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert r.status_code == 200
    new = r.json()
    assert new["access_token"]
    assert new["refresh_token"] != body["refresh_token"]
    assert new["expires_in"] == 120 * 60

    # The presented refresh token is single-use.
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert r.status_code == 401

    # The successor token works.
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": new["refresh_token"]})
    assert r.status_code == 200

    # The fresh access token grants access.
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new['access_token']}"})
    assert r.status_code == 200


def test_refresh_rejects_unknown_token(client, db):
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert r.status_code == 401


def test_logout_revokes_refresh_token(client, db):
    headers, body, user = _register_and_login(client, db)
    r = client.post("/api/v1/auth/logout", json={"refresh_token": body["refresh_token"]})
    assert r.status_code == 204

    r = client.post("/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert r.status_code == 401

    # Logout is idempotent for an already-revoked token.
    r = client.post("/api/v1/auth/logout", json={"refresh_token": body["refresh_token"]})
    assert r.status_code == 204


def test_logout_with_rotated_token_only_revokes_that_token(client, db):
    headers, body, user = _register_and_login(client, db)
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert r.status_code == 200
    new = r.json()

    r = client.post("/api/v1/auth/logout", json={"refresh_token": new["refresh_token"]})
    assert r.status_code == 204
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": new["refresh_token"]})
    assert r.status_code == 401

    # The pre-rotation token was already revoked by rotation; using it fails.
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert r.status_code == 401


def test_system_user_cannot_login(client, db):
    """The system posting account must never obtain a JWT (brief 3.6).

    Its password hash is a non-login sentinel whose verification previously
    raised in the password library; it must surface as an ordinary 401.
    """
    r = client.post(
        "/api/v1/auth/token",
        data={"username": "system@chamacore.invalid", "password": "StrongPassword123!"},
    )
    assert r.status_code == 401


def test_expired_access_token_is_rejected(client, db):
    headers, body, user = _register_and_login(client, db)
    settings = get_settings()
    expired = pyjwt.encode(
        {
            "sub": str(user.id),
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            "type": "access",
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401


def test_rotated_refresh_still_works_after_two_refreshes(client, db):
    headers, body, _ = _register_and_login(client, db)
    token = body["refresh_token"]
    for _ in range(3):
        r = client.post("/api/v1/auth/refresh", json={"refresh_token": token})
        assert r.status_code == 200
        token = r.json()["refresh_token"]
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert r.status_code == 401


def test_password_change_revokes_all_sessions(client, db):
    email = "multisession@example.com"
    pwd1 = "InitialPassword123!"
    pwd2 = "ReplacedPassword456!"
    client.post("/api/v1/auth/register", json={"email": email, "password": pwd1})

    # Session A and Session B both login
    r_a = client.post("/api/v1/auth/token", data={"username": email, "password": pwd1})
    assert r_a.status_code == 200
    token_a = r_a.json()["access_token"]
    refresh_a = r_a.json()["refresh_token"]

    r_b = client.post("/api/v1/auth/token", data={"username": email, "password": pwd1})
    assert r_b.status_code == 200
    refresh_b = r_b.json()["refresh_token"]

    # Session A changes password
    chg = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"current_password": pwd1, "new_password": pwd2},
    )
    assert chg.status_code == 200

    # Session B's refresh token is now revoked
    ref_b = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_b})
    assert ref_b.status_code == 401

    # Session A's old refresh token is also revoked
    ref_a = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_a})
    assert ref_a.status_code == 401

    # Login with new password issues fresh working session
    new_login = client.post("/api/v1/auth/token", data={"username": email, "password": pwd2})
    assert new_login.status_code == 200
    assert new_login.json()["access_token"]


def test_account_deletion_deactivates_user_and_revokes_all_sessions(client, db):
    from app.models.audit_event import AuditEvent

    email = "delete_me@example.com"
    pwd = "DeletePassword123!"
    client.post("/api/v1/auth/register", json={"email": email, "password": pwd})

    login = client.post("/api/v1/auth/token", data={"username": email, "password": pwd})
    assert login.status_code == 200
    access_token = login.json()["access_token"]
    refresh_token = login.json()["refresh_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Wrong password rejected
    wrong = client.post("/api/v1/auth/delete-account", headers=headers, json={"password": "WrongPassword999!"})
    assert wrong.status_code == 400

    # Correct password succeeds with 204
    ok = client.post("/api/v1/auth/delete-account", headers=headers, json={"password": pwd})
    assert ok.status_code == 204

    # Subsequent access with previous token fails immediately (is_active is False)
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 401

    # Refresh token fails
    ref = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert ref.status_code == 401

    # Subsequent login fails
    login_again = client.post("/api/v1/auth/token", data={"username": email, "password": pwd})
    assert login_again.status_code == 401

    # Audit event is recorded
    event = db.scalars(
        select(AuditEvent).where(AuditEvent.action == "auth.account_delete")
    ).first()
    assert event is not None

    # User row is deactivated, not hard-deleted
    user = db.scalars(select(User).where(User.email == email)).one()
    assert user.is_active is False

