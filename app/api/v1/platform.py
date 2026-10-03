"""Platform administration endpoints (cross-Chama; PLATFORM_ADMIN only)."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_platform_admin
from app.db.session import get_db
from app.models.enums import ChamaStatus, RoleName
from app.models.user import User
from app.schemas.platform import (
    PlatformChamaOut,
    PlatformChamaStatusUpdate,
    PlatformStatsOut,
    PlatformUserOut,
)
from app.services.platform import PlatformService

router = APIRouter(prefix="/platform", tags=["platform"])


@router.get("/stats", response_model=PlatformStatsOut)
def platform_stats(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return PlatformService(db).stats(actor=actor)


@router.get("/chamas", response_model=list[PlatformChamaOut])
def list_platform_chamas(
    status: ChamaStatus | None = Query(default=None),
    search: str | None = Query(default=None, max_length=255),
    limit: int | None = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return PlatformService(db).list_chamas(
        actor=actor, status=status, search=search, limit=limit, offset=offset
    )


@router.get("/chamas/{chama_id}", response_model=PlatformChamaOut)
def get_platform_chama(
    chama_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return PlatformService(db).get_chama(actor=actor, chama_id=chama_id)


@router.patch("/chamas/{chama_id}/status", response_model=PlatformChamaOut)
def update_platform_chama_status(
    chama_id: uuid.UUID,
    data: PlatformChamaStatusUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return PlatformService(db).update_chama_status(
        actor=actor, chama_id=chama_id, data=data
    )


@router.get("/users", response_model=list[PlatformUserOut])
def list_platform_users(
    search: str | None = Query(default=None, max_length=255),
    limit: int | None = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return PlatformService(db).list_users(
        actor=actor, search=search, limit=limit, offset=offset
    )


@router.post(
    "/users/{user_id}/roles/{role}", response_model=PlatformUserOut, status_code=201
)
def grant_platform_role(
    user_id: uuid.UUID,
    role: RoleName,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return PlatformService(db).grant_platform_admin(
        actor=actor, user_id=user_id, role=role
    )


@router.delete("/users/{user_id}/roles/{role}", response_model=PlatformUserOut)
def revoke_platform_role(
    user_id: uuid.UUID,
    role: RoleName,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return PlatformService(db).revoke_platform_admin(
        actor=actor, user_id=user_id, role=role
    )


@router.post("/users/{user_id}/require-password-change", response_model=PlatformUserOut)
def require_password_change(
    user_id: uuid.UUID,
    reason: str | None = Query(default=None, max_length=500),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return PlatformService(db).require_password_change(
        actor=actor, user_id=user_id, reason=reason
    )