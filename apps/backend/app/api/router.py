"""Main API router composed from versioned routers."""

from fastapi import APIRouter

from app.api.v1.router import router as v1_router
from app.core.config import get_settings

settings = get_settings()

router = APIRouter()
router.include_router(v1_router, prefix=settings.api_v1_prefix)
