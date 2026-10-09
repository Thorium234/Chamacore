"""Authentication service."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError, StateError
from app.core.password_policy import validate_password
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.user import User
from app.repositories.member import MemberRepository
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository
from app.schemas.chama import MemberDetails
from app.services.audit import AuditAction, AuditService


def _as_aware(value: datetime) -> datetime:
    """Normalize timestamps read back from the database.

    ``DateTime(timezone=True)`` keeps aware values on PostgreSQL but SQLite
    stores and returns naive datetimes, so comparisons need normalization.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.members = MemberRepository(db)
        self.refresh_tokens = RefreshTokenRepository(db)
        self.audit = AuditService(db)

    def register(
        self, *, email: str, password: str, member: MemberDetails
    ) -> User:
        if self.users.get_by_email(email) is not None:
            raise ConflictError("An account with this email already exists")
        existing_member = self.members.find_by_identity(
            member.phone_number, member.government_id
        )
        if existing_member is None:
            if self.members.phone_exists(member.phone_number):
                raise ConflictError("phone_number is already registered to another member")
            if self.members.government_id_exists(member.government_id):
                raise ConflictError("government_id is already registered to another member")
        elif self.users.get_by_member_id(existing_member.id) is not None:
            raise ConflictError("This member identity is already linked to another account")

        validate_password(password, email=email, phone=member.phone_number)
        if existing_member is None:
            existing_member = self.members.create(member)
        user = self.users.create(email=email, password_hash=hash_password(password))
        user.member_id = existing_member.id
        self.db.commit()
        self.audit.record_commit(
            actor=user,
            chama_id=None,
            action=AuditAction.AUTH_REGISTER,
            resource_type="user",
            resource_id=user.id,
        )
        return user

    def authenticate(self, *, identifier: str, password: str) -> User | None:
        if not identifier or not password:
            return None
        identifier_norm = identifier.strip()
        user = self.users.get_by_email(identifier_norm)
        if user is None:
            from app.core.phone import normalize_ke_msisdn

            try:
                phone_norm = normalize_ke_msisdn(identifier_norm)
            except Exception:
                phone_norm = identifier_norm
            user = self.users.get_by_phone(phone_norm) or self.users.get_by_phone(identifier_norm)
        if user is None:
            user = self.users.get_by_government_id(identifier_norm)
        if user is None or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    def link_member(self, *, user: User, phone_number: str, government_id: str) -> User:
        """Link the authenticated user to their member identity (approved decision)."""
        if user.member_id is not None:
            raise ConflictError("This account is already linked to a member")
        member = self.members.find_by_identity(phone_number, government_id)
        if member is None:
            raise NotFoundError("No member matches these identity details")
        existing = self.users.get_by_member_id(member.id)
        if existing is not None:
            raise ConflictError("This member identity is already linked to another account")
        user.member_id = member.id
        self.db.commit()
        self.audit.record_commit(
            actor=user,
            chama_id=None,
            action=AuditAction.AUTH_MEMBER_LINK,
            resource_type="user",
            resource_id=user.id,
        )
        return user

    def issue_token(self, user: User) -> str:
        return create_access_token(subject=str(user.id))

    def create_auth_session(self, user: User) -> dict[str, str]:
        """Open a session: a fresh access token plus a stored refresh token."""
        settings = get_settings()
        refresh_token = generate_refresh_token()
        self.refresh_tokens.create(
            user_id=user.id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.refresh_token_expires_days),
        )
        self.db.commit()
        return {
            "access_token": self.issue_token(user),
            "refresh_token": refresh_token,
            "must_change_password": user.must_change_password,
        }

    def change_password(
        self, *, user: User, current_password: str, new_password: str
    ) -> User:
        """Replace the caller's password and clear the forced-change flag.

        Every existing refresh token is revoked so a password change ends all
        other sessions immediately; the caller keeps working with the access
        token it already holds.
        """
        if not verify_password(current_password, user.password_hash):
            raise StateError("The current password is incorrect")
        validate_password(
            new_password,
            email=user.email,
            phone=user.member.phone_number if user.member is not None else None,
        )
        user.must_change_password = False
        user.password_hash = hash_password(new_password)
        self.refresh_tokens.revoke_all_for_user(
            user.id, revoked_at=datetime.now(timezone.utc)
        )
        self.audit.record_commit(
            actor=user,
            chama_id=None,
            action=AuditAction.AUTH_PASSWORD_CHANGE,
            resource_type="user",
            resource_id=user.id,
        )
        return user

    def require_password_change(self, *, user: User, reason: str | None = None) -> User:
        """Force the user to change their password at next login."""
        if not user.must_change_password:
            user.must_change_password = True
            self.db.commit()
            self.audit.record_commit(
                actor=None,
                chama_id=None,
                action=AuditAction.AUTH_PASSWORD_CHANGE_REQUIRED,
                resource_type="user",
                resource_id=user.id,
                payload={"reason": reason} if reason else None,
            )
        return user

    def rotate_refresh_token(self, *, refresh_token: str) -> dict[str, str]:
        """Exchange a valid refresh token for a new access + refresh pair.

        The presented token is single-use: it is revoked and a successor is
        issued, so a stolen token cannot be replayed after first use.
        """
        settings = get_settings()
        token = self.refresh_tokens.get_by_hash(hash_refresh_token(refresh_token))
        now = datetime.now(timezone.utc)
        if token is None or token.revoked_at is not None:
            raise StateError("This refresh token is invalid or has already been used")
        if _as_aware(token.expires_at) <= now:
            self.refresh_tokens.revoke(token, revoked_at=now)
            self.db.commit()
            raise StateError("This refresh token has expired")

        user = self.users.get_by_id(token.user_id)
        if user is None or not user.is_active:
            raise StateError("This refresh token is no longer valid")
        must_change_password = user.must_change_password

        self.refresh_tokens.revoke(token, revoked_at=now)
        new_refresh = generate_refresh_token()
        self.refresh_tokens.create(
            user_id=user.id,
            token_hash=hash_refresh_token(new_refresh),
            expires_at=now + timedelta(days=settings.refresh_token_expires_days),
        )
        self.db.commit()
        self.audit.record_commit(
            actor=user,
            chama_id=None,
            action=AuditAction.AUTH_REFRESH,
            resource_type="user",
            resource_id=user.id,
        )
        return {
            "access_token": self.issue_token(user),
            "refresh_token": new_refresh,
            "must_change_password": must_change_password,
        }

    def revoke_refresh_token(self, *, refresh_token: str) -> None:
        """Revoke the presented refresh token (logout). Idempotent."""
        token = self.refresh_tokens.get_by_hash(hash_refresh_token(refresh_token))
        if token is None or token.revoked_at is not None:
            return
        self.refresh_tokens.revoke(token, revoked_at=datetime.now(timezone.utc))
        self.db.commit()
