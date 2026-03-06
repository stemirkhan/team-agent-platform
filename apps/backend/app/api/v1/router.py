"""Versioned API router."""

from fastapi import APIRouter

from app.api.v1 import agents, auth, health, me, teams

router = APIRouter()
router.include_router(health.router)
router.include_router(auth.router)
router.include_router(me.router)
router.include_router(agents.router)
router.include_router(teams.router)
