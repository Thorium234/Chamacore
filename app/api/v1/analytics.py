"""Role-scoped analytics endpoints."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.analytics import CollectionAnalyticsOut
from app.services.analytics import AnalyticsService

router = APIRouter(tags=["analytics"])


@router.get(
    "/chamas/{chama_id}/analytics/collections",
    response_model=CollectionAnalyticsOut,
)
def collection_analytics(
    chama_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return AnalyticsService(db).collections(actor=actor, chama_id=chama_id)
