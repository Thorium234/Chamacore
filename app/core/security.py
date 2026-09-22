"""Password hashing and JWT token helpers."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.core.config import get_settings

password_hash = PasswordHash.recommended()


def hash_password(plain_password: str) -> str:
    return password_hash.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return password_hash.verify(plain_password, hashed_password)
    except UnknownHashError:
        # A stored hash that is not a supported scheme (for example the
        # non-login sentinel on system@chamacore.invalid) must fail closed as
        # a bad credential, never crash the login path.
        return False


def create_access_token(subject: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expires_minutes)
    payload: dict[str, Any] = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
    subject = payload.get("sub")
    return subject if isinstance(subject, str) else None


def generate_refresh_token() -> str:
    """Return a new opaque refresh token (128 bits of entropy, URL-safe)."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(refresh_token: str) -> str:
    """Return the SHA-256 digest stored server-side for a refresh token."""
    return hashlib.sha256(refresh_token.encode("ascii")).hexdigest()