"""In-app notification service.

Notifications are the user-facing projection of business audit events. The
audit trail stays authoritative and immutable; this service only derives a
readable, per-user feed from it so the client can render a notification centre.

Fan-out rule: an audited action notifies the users it concerns, not the whole
Chama. Membership, role, financial, and payment actions notify the affected
member; Chama lifecycle changes notify the platform administrators; an action
the actor performed on themselves does not notify the actor. Delivery is
in-app only; no channel sends anything externally.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.enums import MembershipStatus, NotificationChannel, RoleName
from app.models.membership import Membership
from app.models.notification import Notification
from app.models.user import User
from app.repositories.notification import NotificationRepository

# Actions that concern the whole Chama. They are broadcast to the Chama's
# active members, minus the actor.
CHAMA_BROADCAST_ACTIONS = frozenset(
    {
        "chama.update",
        "membership.create",
        "role.assign",
        "role.remove",
        "payment_connection.created",
        "payment_connection.validated",
        "payment_connection.enabled",
        "payment_connection.disabled",
        "payment_connection.credentials_replaced",
        "payment_connection.deleted",
        "c2b.registration",
    }
)

# Actions that concern the platform rather than any single Chama, so they go to
# the platform administrators.
PLATFORM_ACTIONS = frozenset(
    {
        "chama.create",
        "chama.status_change",
        "platform.chama_status_change",
        "platform.admin_granted",
        "platform.admin_revoked",
        "auth.password_change_required",
    }
)

_TITLES = {
    "chama.create": "Chama created",
    "chama.update": "Chama details updated",
    "chama.status_change": "Chama status changed",
    "membership.create": "New membership registered",
    "membership.status_change": "Membership status changed",
    "role.assign": "Role assigned",
    "role.remove": "Role removed",
    "contribution.create": "Contribution recorded",
    "contribution.confirm": "Contribution confirmed",
    "contribution.reverse": "Contribution reversed",
    "registration_fee.pay": "Registration fee paid",
    "registration_fee.pay_reversal": "Registration fee payment reversed",
    "registration_fee.waive": "Registration fee waived",
    "loan.apply": "Loan application submitted",
    "loan.submit": "Loan submitted for approval",
    "loan.approve": "Loan approved",
    "loan.reject": "Loan rejected",
    "loan.cancel": "Loan cancelled",
    "loan.disburse": "Loan disbursed",
    "loan.repayment": "Loan repayment confirmed",
    "loan.repayment_reversal": "Loan repayment reversed",
    "payout.request": "Payout requested",
    "payout.approve": "Payout approved",
    "payout.reject": "Payout rejected",
    "payout.process": "Payout processing",
    "payout.complete": "Payout completed",
    "payout.fail": "Payout failed",
    "payout.reversal": "Payout reversed",
    "auth.password_change_required": "Password change required",
}


class NotificationService:
    def __init__(self, db: Session):
        self.db = db
        self.notifications = NotificationRepository(db)

    def notify(
        self,
        *,
        user_id: uuid.UUID,
        action: str,
        actor_user_id: uuid.UUID | None = None,
        chama_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: uuid.UUID | None = None,
        payload: dict | None = None,
        title: str | None = None,
        body: str | None = None,
    ) -> Notification:
        """Create one in-app notification in the caller's transaction."""
        return self.notifications.create(
            user_id=user_id,
            channel=NotificationChannel.IN_APP,
            action=action,
            title=title or _TITLES.get(action, action),
            body=body,
            chama_id=chama_id,
            resource_type=resource_type,
            resource_id=resource_id,
            actor_user_id=actor_user_id,
            payload=payload,
            is_read=False,
            created_at=datetime.now(timezone.utc),
        )

    def fan_out(
        self,
        *,
        action: str,
        actor: User | None,
        chama_id: uuid.UUID | None,
        subject_member_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: uuid.UUID | None = None,
        payload: dict | None = None,
    ) -> list[Notification]:
        """Notify everyone concerned by an audited action.

        Returns the created notifications. Never raises for delivery reasons:
        a notification failure must not roll back the audited business action.
        """
        if action in PLATFORM_ACTIONS or chama_id is None:
            recipient_ids = self._platform_admin_ids()
        elif action in CHAMA_BROADCAST_ACTIONS:
            # Broadcast: the whole membership should know, not just the subject.
            recipient_ids = self._active_member_user_ids(chama_id)
        elif subject_member_id is not None:
            recipient_ids = self._user_ids_for_member(subject_member_id)
        else:
            recipient_ids = self._active_member_user_ids(chama_id)

        actor_id = actor.id if actor is not None else None
        created: list[Notification] = []
        for user_id in recipient_ids:
            if actor_id is not None and user_id == actor_id:
                continue
            created.append(
                self.notify(
                    user_id=user_id,
                    action=action,
                    actor_user_id=actor_id,
                    chama_id=chama_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    payload=payload,
                )
            )
        return created

    def list_for_user(
        self,
        *,
        user: User,
        limit: int | None = None,
        offset: int = 0,
        unread_only: bool = False,
        chama_id: uuid.UUID | None = None,
    ) -> list[Notification]:
        return self.notifications.list_for_user(
            user.id,
            limit=limit,
            offset=offset,
            unread_only=unread_only,
            chama_id=chama_id,
        )

    def count_unread(self, *, user: User) -> int:
        return self.notifications.count_unread(user.id)

    def mark_read(self, *, user: User, notification_id: uuid.UUID) -> Notification:
        notification = self.notifications.get_for_user(user.id, notification_id)
        if notification is None:
            raise NotFoundError("Notification not found")
        if not notification.is_read:
            self.notifications.mark_read(
                notification, read_at=datetime.now(timezone.utc)
            )
        return notification

    def mark_all_read(self, *, user: User) -> int:
        return self.notifications.mark_all_read(
            user.id, read_at=datetime.now(timezone.utc)
        )

    # -- recipient resolution -------------------------------------------------

    def _platform_admin_ids(self) -> list[uuid.UUID]:
        from app.repositories.user_platform_role import UserPlatformRoleRepository

        return UserPlatformRoleRepository(self.db).list_admin_user_ids(
            role=RoleName.PLATFORM_ADMIN
        )

    def _user_ids_for_member(self, member_id: uuid.UUID) -> list[uuid.UUID]:
        stmt = select(User.id).where(
            User.member_id == member_id, User.is_active.is_(True)
        )
        return list(self.db.scalars(stmt))

    def _active_member_user_ids(self, chama_id: uuid.UUID) -> list[uuid.UUID]:
        stmt = (
            select(User.id)
            .join(Membership, Membership.member_id == User.member_id)
            .where(
                Membership.chama_id == chama_id,
                Membership.status == MembershipStatus.ACTIVE,
                User.is_active.is_(True),
            )
            .distinct()
        )
        return list(self.db.scalars(stmt))