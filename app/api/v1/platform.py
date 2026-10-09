"""Platform administration endpoints (cross-Chama; PLATFORM_ADMIN only)."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.enums import ChamaStatus, RoleName
from app.models.user import User
from app.schemas.platform import (
    PlatformAdminGrantRequest,
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


@router.get("/admins", response_model=list[PlatformUserOut])
def list_platform_admins(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return PlatformService(db).list_admins(actor=actor)


@router.get("/users", response_model=list[PlatformUserOut])
def search_platform_users(
    search: str = Query(min_length=1, max_length=255),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return PlatformService(db).search_users(
        actor=actor, search=search, limit=limit, offset=offset
    )


@router.post("/users/{user_id}/require-password-change", response_model=PlatformUserOut)
def require_platform_user_password_change(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return PlatformService(db).require_password_change(actor=actor, user_id=user_id)


@router.post("/users/{user_id}/deactivate", response_model=PlatformUserOut)
def deactivate_platform_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return PlatformService(db).set_user_active(
        actor=actor, user_id=user_id, is_active=False
    )


@router.post("/users/{user_id}/reactivate", response_model=PlatformUserOut)
def reactivate_platform_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return PlatformService(db).set_user_active(
        actor=actor, user_id=user_id, is_active=True
    )


@router.post("/admins", response_model=PlatformUserOut, status_code=201)
def grant_platform_admin(
    data: PlatformAdminGrantRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return PlatformService(db).grant_platform_admin_by_email(actor=actor, data=data)


@router.delete("/admins/{user_id}", response_model=PlatformUserOut)
def revoke_platform_admin(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return PlatformService(db).revoke_platform_admin(
        actor=actor, user_id=user_id, role=RoleName.PLATFORM_ADMIN
    )
