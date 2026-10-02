"""In-app notification endpoints."""

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.notification import (
    MarkAllReadOut,
    NotificationOut,
    UnreadCountOut,
)
from app.services.notification import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    unread_only: bool = Query(default=False),
    chama_id: uuid.UUID | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return NotificationService(db).list_for_user(
        user=actor,
        limit=limit,
        offset=offset,
        unread_only=unread_only,
        chama_id=chama_id,
    )


@router.get("/unread-count", response_model=UnreadCountOut)
def unread_count(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return UnreadCountOut(unread_count=NotificationService(db).count_unread(user=actor))


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    service = NotificationService(db)
    notification = service.mark_read(user=actor, notification_id=notification_id)
    db.commit()
    return notification


@router.post("/read-all", response_model=MarkAllReadOut)
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    service = NotificationService(db)
    updated = service.mark_all_read(user=actor)
    db.commit()
    return MarkAllReadOut(updated=updated)


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    """Notifications are user-owned; deleting one only affects the caller's feed."""
    service = NotificationService(db)
    notification = service.notifications.get_for_user(actor.id, notification_id)
    if notification is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    db.delete(notification)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)