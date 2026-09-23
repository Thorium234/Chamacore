"""Authentication service."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError, StateError
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

    def register(self, *, email: str, password: str) -> User:
        if self.users.get_by_email(email) is not None:
            raise ConflictError("An account with this email already exists")
        user = self.users.create(email=email, password_hash=hash_password(password))
        self.db.commit()
        self.audit.record_commit(
            actor=user,
            chama_id=None,
            action=AuditAction.AUTH_REGISTER,
            resource_type="user",
            resource_id=user.id,
        )
        return user

    def authenticate(self, *, email: str, password: str) -> User | None:
        user = self.users.get_by_email(email)
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
        return {"access_token": self.issue_token(user), "refresh_token": refresh_token}

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
        return {"access_token": self.issue_token(user), "refresh_token": new_refresh}

    def revoke_refresh_token(self, *, refresh_token: str) -> None:
        """Revoke the presented refresh token (logout). Idempotent."""
        token = self.refresh_tokens.get_by_hash(hash_refresh_token(refresh_token))
        if token is None or token.revoked_at is not None:
            return
        self.refresh_tokens.revoke(token, revoked_at=datetime.now(timezone.utc))
        self.db.commit()