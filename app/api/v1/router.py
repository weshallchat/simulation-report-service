"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1 import simulations, reports, auth

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(simulations.router, prefix="/simulations", tags=["Simulations"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
