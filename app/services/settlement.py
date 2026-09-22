"""Settlement of a contribution linked to a payment intent (ADR-019).

When a payment intent that carries a ``contribution_id`` reaches SUCCEEDED, the
linked PENDING contribution is confirmed and posted to the ledger as the system
user (OQ-013). Settlement is safe to call multiple times: if the contribution
is already CONFIRMED it is returned as-is.
"""

from sqlalchemy.orm import Session

from app.core.errors import StateError
from app.db.bootstrap import ensure_system_user
from app.models.payment_intent import PaymentIntent
from app.repositories.contribution import ContributionRepository
from app.services.contribution import ContributionService


def settle_linked_contribution(db: Session, *, payment_intent: PaymentIntent) -> bool:
    """Confirm and post the intent's linked contribution.

    Returns ``True`` when a contribution was settled, ``False`` when the intent
    has no linked contribution.
    """
    if payment_intent.contribution_id is None:
        return False
    contribution = ContributionRepository(db).get_by_id(payment_intent.contribution_id)
    if contribution is None:
        raise StateError("A payment succeeded but its linked contribution no longer exists")
    if contribution.membership_id != payment_intent.membership_id:
        raise StateError("A payment succeeded but its linked contribution belongs to a different membership")
    if contribution.membership.chama_id != payment_intent.chama_id:
        raise StateError("A payment succeeded but its linked contribution belongs to a different Chama")
    ContributionService(db)._settle(
        contribution,
        ensure_system_user(db),
        allow_already_confirmed=True,
    )
    return True