"""Idempotent bootstrap for the first global platform administrator.

The bootstrap credentials are read only from ``CHAMACORE_BOOTSTRAP_*``
settings (normally an ignored local ``.env`` file or deployment secrets).
They are never written to migration source or logs. Existing credentials are
not overwritten, so rerunning Alembic or this fallback cannot reset a changed
password.
"""

from datetime import datetime, timezone
import uuid

from sqlalchemy import DateTime, Uuid, bindparam, text
from sqlalchemy.engine import Connection

from app.core.config import Settings
from app.core.password_policy import validate_password
from app.core.phone import normalize_ke_msisdn
from app.core.security import hash_password


def ensure_bootstrap_platform_admin(connection: Connection, settings: Settings) -> str:
    email = (settings.bootstrap_platform_admin_email or "").strip().lower()
    password = (
        settings.bootstrap_platform_admin_password.get_secret_value()
        if settings.bootstrap_platform_admin_password
        else ""
    )
    raw_phone = (settings.bootstrap_platform_admin_phone or "").strip()
    government_id = (settings.bootstrap_platform_admin_government_id or "").strip()
    supplied = (email, password, raw_phone, government_id)
    if not any(supplied):
        return "not_configured"
    if not all(supplied):
        raise RuntimeError("Bootstrap platform administrator settings are incomplete")
    if "@" not in email:
        raise RuntimeError("Bootstrap platform administrator email is invalid")

    phone = normalize_ke_msisdn(raw_phone)
    if not phone.startswith("254") or len(phone) != 12:
        raise RuntimeError("Bootstrap platform administrator phone is invalid")
    validate_password(password, email=email, phone=phone)

    phone_member = connection.execute(
        text("SELECT id, government_id FROM members WHERE phone_number = :phone"),
        {"phone": phone},
    ).mappings().first()
    id_member = connection.execute(
        text("SELECT id, phone_number FROM members WHERE government_id = :government_id"),
        {"government_id": government_id},
    ).mappings().first()
    if phone_member and id_member and phone_member["id"] != id_member["id"]:
        raise RuntimeError("Bootstrap phone and government ID belong to different members")
    member = phone_member or id_member
    if member:
        if phone_member and phone_member["government_id"] != government_id:
            raise RuntimeError("Bootstrap phone is already registered to another identity")
        if id_member and id_member["phone_number"] != phone:
            raise RuntimeError("Bootstrap government ID is already registered to another identity")
        member_id = uuid.UUID(str(member["id"]))
    else:
        member_id = uuid.uuid4()
        connection.execute(
            text(
                "INSERT INTO members (id, first_name, last_name, phone_number, government_id) "
                "VALUES (:id, :first_name, :last_name, :phone, :government_id)"
            ).bindparams(bindparam("id", type_=Uuid())),
            {
                "id": member_id,
                "first_name": settings.bootstrap_platform_admin_first_name.strip() or "Platform",
                "last_name": settings.bootstrap_platform_admin_last_name.strip() or "Developer",
                "phone": phone,
                "government_id": government_id,
            },
        )

    user = connection.execute(
        text("SELECT id, member_id FROM users WHERE lower(email) = :email"),
        {"email": email},
    ).mappings().first()
    created = user is None
    if user is None:
        user_id = uuid.uuid4()
        connection.execute(
            text(
                "INSERT INTO users "
                "(id, email, password_hash, is_active, must_change_password, member_id) "
                "VALUES (:id, :email, :password_hash, :is_active, :must_change_password, :member_id)"
            ).bindparams(
                bindparam("id", type_=Uuid()), bindparam("member_id", type_=Uuid())
            ),
            {
                "id": user_id,
                "email": email,
                "password_hash": hash_password(password),
                "is_active": True,
                "must_change_password": True,
                "member_id": member_id,
            },
        )
    else:
        user_id = uuid.UUID(str(user["id"]))
        existing_member_id = uuid.UUID(str(user["member_id"])) if user["member_id"] else None
        if existing_member_id and existing_member_id != member_id:
            raise RuntimeError("Bootstrap email is linked to a different member identity")
        if existing_member_id is None:
            already_linked = connection.execute(
                text("SELECT id FROM users WHERE member_id = :member_id AND id != :user_id").bindparams(
                    bindparam("member_id", type_=Uuid()), bindparam("user_id", type_=Uuid())
                ),
                {"member_id": member_id, "user_id": user_id},
            ).first()
            if already_linked:
                raise RuntimeError("Bootstrap member identity is linked to another account")
            connection.execute(
                text("UPDATE users SET member_id = :member_id WHERE id = :user_id").bindparams(
                    bindparam("member_id", type_=Uuid()), bindparam("user_id", type_=Uuid())
                ),
                {"member_id": member_id, "user_id": user_id},
            )

    connection.execute(
        text(
            "INSERT INTO user_platform_roles "
            "(id, user_id, role, granted_by_user_id, granted_at) "
            "VALUES (:id, :user_id, 'PLATFORM_ADMIN', NULL, :granted_at) "
            "ON CONFLICT (user_id, role) DO NOTHING"
        ).bindparams(
            bindparam("id", type_=Uuid()),
            bindparam("user_id", type_=Uuid()),
            bindparam("granted_at", type_=DateTime(timezone=True)),
        ),
        {
            "id": uuid.uuid4(),
            "user_id": user_id,
            "granted_at": datetime.now(timezone.utc),
        },
    )
    return "created" if created else "reconciled"


def main() -> None:
    """Fallback command for databases where Alembic already passed the seed revision."""
    from app.db.session import engine

    with engine.begin() as connection:
        result = ensure_bootstrap_platform_admin(connection, Settings())
    print(f"Bootstrap platform administrator: {result}")


if __name__ == "__main__":
    main()
