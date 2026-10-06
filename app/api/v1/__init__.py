"""Роутер версии API v1."""

from fastapi import APIRouter

from app.api.v1.payments import router as payments_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(payments_router)
