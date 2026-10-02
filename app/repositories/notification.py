"""Notification repository."""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.notification import Notification


class NotificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **fields) -> Notification:
        notification = Notification(**fields)
        self.db.add(notification)
        self.db.flush()
        return notification

    def get_for_user(
        self, user_id: uuid.UUID, notification_id: uuid.UUID
    ) -> Notification | None:
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        return self.db.scalars(stmt).first()

    def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        limit: int | None = None,
        offset: int = 0,
        unread_only: bool = False,
        chama_id: uuid.UUID | None = None,
    ) -> list[Notification]:
        stmt = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            stmt = stmt.where(Notification.is_read.is_(False))
        if chama_id is not None:
            stmt = stmt.where(Notification.chama_id == chama_id)
        stmt = stmt.order_by(Notification.created_at.desc(), Notification.id)
        if limit is not None:
            stmt = stmt.limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def count_unread(self, user_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        return int(self.db.scalar(stmt) or 0)

    def mark_read(
        self, notification: Notification, *, read_at: datetime
    ) -> Notification:
        notification.is_read = True
        notification.read_at = read_at
        self.db.flush()
        return notification

    def mark_all_read(self, user_id: uuid.UUID, *, read_at: datetime) -> int:
        stmt = select(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        rows = list(self.db.scalars(stmt))
        for row in rows:
            row.is_read = True
            row.read_at = read_at
        self.db.flush()
        return len(rows)