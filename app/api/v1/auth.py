"""Authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import (
    check_member_link_rate_limit,
    check_register_rate_limit,
    check_token_rate_limit,
    get_current_user,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import MemberLinkRequest, RegisterRequest, TokenOut, UserOut
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenOut(access_token=service.issue_token(user))


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