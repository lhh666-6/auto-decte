"""Aggregate production mobile API routers without process-local state."""

from fastapi import APIRouter

from app.api.routers import (
    mobile_auth_ds,
    mobile_bamboo_ds,
    mobile_context_ds,
    mobile_definitions_ds,
    mobile_submissions_ds,
)

router = APIRouter(prefix="/api/v1/mobile", tags=["mobile"])
router.include_router(mobile_auth_ds.router)
router.include_router(mobile_bamboo_ds.router)
router.include_router(mobile_definitions_ds.router)
router.include_router(mobile_context_ds.router)
router.include_router(mobile_submissions_ds.router)
