"""API dependencies."""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
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