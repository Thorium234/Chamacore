"""Aggregates all V1 routers."""

from fastapi import APIRouter, Depends

from app.api.deps import check_general_rate_limit
from app.api.v1 import (
    auth,
    chamas,
    contributions,
    ledger,
    memberships,
    payments,
    payments_webhooks,
    registration_fees,
    roles,
    shares,
)

api_router = APIRouter(dependencies=[Depends(check_general_rate_limit)])
api_router.include_router(auth.router)
api_router.include_router(chamas.router)
api_router.include_router(memberships.router)
api_router.include_router(roles.router)
api_router.include_router(registration_fees.router)
api_router.include_router(contributions.router)
api_router.include_router(shares.router)
api_router.include_router(ledger.router)
api_router.include_router(payments.router)
api_router.include_router(payments_webhooks.router)