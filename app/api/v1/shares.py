"""Share endpoints."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.membership import ShareOut
from app.services.share import ShareService

router = APIRouter(tags=["shares"])


@router.get("/chamas/{chama_id}/memberships/{membership_id}/shares", response_model=list[ShareOut])
def list_shares(
    chama_id: uuid.UUID,
    membership_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    shares = ShareService(db).list_for_membership(
        actor=actor, chama_id=chama_id, membership_id=membership_id
    )
    return [ShareOut.model_validate(share) for share in shares]