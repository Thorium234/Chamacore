"""System user used for trustworthy, actor-less ledger postings.

Money-in events confirmed by an authorized provider (STK success callbacks and
manual C2B Paybill confirmations) are posted to the ledger by a dedicated,
non-login system account (OQ-013, ADR-019). The row is seeded by migration
``f2b4d6a8e0c1`` and by the test ``db`` fixture.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User

SYSTEM_USER_EMAIL = "system@chamacore.invalid"
SYSTEM_USER_UUID = uuid.UUID("6f1c3a5e-0000-4000-8000-0000000000a1")


def system_user_id() -> uuid.UUID:
    return SYSTEM_USER_UUID


def ensure_system_user(db: Session) -> User:
    """Return the system user, creating it in this session if absent."""
    user = db.scalars(select(User).where(User.email == SYSTEM_USER_EMAIL)).first()
    if user is not None:
        return user
    user = User(
        id=SYSTEM_USER_UUID,
        email=SYSTEM_USER_EMAIL,
        password_hash="!system-account-no-login!",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user