"""Aggregates all V1 routers."""

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    chamas,
    contributions,
    memberships,
    registration_fees,
    roles,
    shares,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(chamas.router)
api_router.include_router(memberships.router)
api_router.include_router(roles.router)
api_router.include_router(registration_fees.router)
api_router.include_router(contributions.router)
api_router.include_router(shares.router)