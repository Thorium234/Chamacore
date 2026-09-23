"""Authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import (
    check_member_link_rate_limit,
    check_register_rate_limit,
    check_token_rate_limit,
    get_current_user,
)
from app.core.config import get_settings
from app.core.errors import StateError
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import LogoutRequest, MemberLinkRequest, RefreshRequest, RegisterRequest, TokenOut, UserOut
from app.services.audit import AuditAction, AuditService
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db),
    _rate_limit: None = Depends(check_register_rate_limit),
) -> User:
    return AuthService(db).register(email=data.email, password=data.password)


@router.post("/token", response_model=TokenOut)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    _rate_limit: None = Depends(check_token_rate_limit),
) -> TokenOut:
    service = AuthService(db)
    user = service.authenticate(email=form_data.username, password=form_data.password)
    if user is None:
        AuditService(db).record_commit(
            actor=None,
            chama_id=None,
            action=AuditAction.AUTH_LOGIN_FAILED,
            resource_type="user",
            success=False,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    session = service.create_auth_session(user)
    AuditService(db).record_commit(
        actor=user,
        chama_id=None,
        action=AuditAction.AUTH_LOGIN,
        resource_type="user",
        resource_id=user.id,
    )
    return _to_token_out(session)


@router.post("/refresh", response_model=TokenOut)
def refresh(
    data: RefreshRequest,
    db: Session = Depends(get_db),
    _rate_limit: None = Depends(check_token_rate_limit),
) -> TokenOut:
    try:
        session = AuthService(db).rotate_refresh_token(refresh_token=data.refresh_token)
    except StateError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _to_token_out(session)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    data: LogoutRequest,
    db: Session = Depends(get_db),
    _rate_limit: None = Depends(check_token_rate_limit),
) -> Response:
    AuthService(db).revoke_refresh_token(refresh_token=data.refresh_token)
    AuditService(db).record_commit(
        actor=None,
        chama_id=None,
        action=AuditAction.AUTH_LOGOUT,
        resource_type="refresh_token",
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/me/member-link", response_model=UserOut)
def link_me_to_member(
    data: MemberLinkRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    _rate_limit: None = Depends(check_member_link_rate_limit),
) -> User:
    return AuthService(db).link_member(
        user=actor, phone_number=data.phone_number, government_id=data.government_id
    )


@router.get("/me", response_model=UserOut)
def me(actor: User = Depends(get_current_user)) -> User:
    return actor


def _to_token_out(session: dict[str, str]) -> TokenOut:
    settings = get_settings()
    return TokenOut(
        access_token=session["access_token"],
        refresh_token=session["refresh_token"],
        expires_in=settings.jwt_expires_minutes * 60,
    )