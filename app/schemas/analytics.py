"""Role-scoped analytics response models."""

from decimal import Decimal

from pydantic import BaseModel


class CollectionAnalyticsMonth(BaseModel):
    month: str
    contributions: Decimal
    registration_fees: Decimal
    total_collected: Decimal


class CollectionAnalyticsOut(BaseModel):
    currency: str = "KES"
    scope: str
    months: list[CollectionAnalyticsMonth]
