"""Versioned API router."""

from fastapi import APIRouter

from app.api.v1 import agents, auth, exports, github, health, host, me, runs, teams, workspaces

router = APIRouter()
router.include_router(health.router)
router.include_router(host.router)
router.include_router(github.router)
router.include_router(workspaces.router)
router.include_router(runs.router)
router.include_router(auth.router)
router.include_router(me.router)
router.include_router(agents.router)
router.include_router(teams.router)
router.include_router(exports.router)
