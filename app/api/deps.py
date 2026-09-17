"""API dependencies."""

import uuid

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import RateLimitError
from app.core.ratelimit import RateLimiter
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.user import UserRepository

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{get_settings().api_v1_prefix}/auth/token",
)

INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

_general_limiter = RateLimiter(get_settings().general_api_per_minute_limit, 60.0)
_register_limiter = RateLimiter(get_settings().auth_register_per_minute_limit, 60.0)
_token_limiter = RateLimiter(get_settings().auth_token_per_minute_limit, 60.0)
_member_link_limiter = RateLimiter(get_settings().auth_member_link_per_minute_limit, 60.0)


def reset_rate_limiters() -> None:
    """Clear in-process limiter windows between tests."""
    for limiter in (
        _general_limiter,
        _register_limiter,
        _token_limiter,
        _member_link_limiter,
    ):
        limiter.reset()


def _client_host_key(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"


def check_general_rate_limit(request: Request) -> None:
    if not _general_limiter.allow(_client_host_key(request)):
        raise RateLimitError("Too many API requests; try again shortly")


def check_register_rate_limit(request: Request) -> None:
    if not _register_limiter.allow(_client_host_key(request)):
        raise RateLimitError("Too many registration requests; try again shortly")


def check_token_rate_limit(request: Request) -> None:
    if not _token_limiter.allow(_client_host_key(request)):
        raise RateLimitError("Too many login attempts; try again shortly")


def check_member_link_rate_limit(request: Request) -> None:
    if not _member_link_limiter.allow(_client_host_key(request)):
        raise RateLimitError("Too many member-link requests; try again shortly")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    subject = decode_access_token(token)
    if subject is None:
        raise INVALID_CREDENTIALS
    try:
        user_id = uuid.UUID(subject)
    except ValueError as exc:
        raise INVALID_CREDENTIALS from exc
    user = UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise INVALID_CREDENTIALS
    return user