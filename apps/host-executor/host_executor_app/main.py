"""Host executor FastAPI entrypoint."""

from __future__ import annotations

import secrets

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from host_executor_app.api.claude import router as claude_router
from host_executor_app.api.codex import router as codex_router
from host_executor_app.api.github import router as github_router
from host_executor_app.api.workspaces import router as workspaces_router
from host_executor_app.core.config import get_settings
from host_executor_app.schemas.host import HostDiagnosticsResponse
from host_executor_app.services.host_diagnostics_service import HostDiagnosticsService

settings = get_settings()
diagnostics_service = HostDiagnosticsService()
HOST_EXECUTOR_SECRET_HEADER = "X-TAP-Executor-Secret"

app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def require_backend_secret(request: Request, call_next):
    """Reject host executor requests that do not present the shared backend secret."""
    if request.url.path == "/healthz":
        return await call_next(request)

    provided_secret = request.headers.get(HOST_EXECUTOR_SECRET_HEADER, "")
    if not secrets.compare_digest(provided_secret, settings.host_executor_shared_secret):
        return JSONResponse(
            status_code=401,
            content={"detail": "Missing or invalid host executor credentials."},
        )

    return await call_next(request)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Return liveness for the host executor bridge."""
    return {"status": "ok"}


@app.get("/diagnostics", response_model=HostDiagnosticsResponse)
def diagnostics() -> HostDiagnosticsResponse:
    """Return host-native tool diagnostics."""
    return diagnostics_service.build_snapshot()


@app.post("/diagnostics/refresh", response_model=HostDiagnosticsResponse)
def refresh_diagnostics() -> HostDiagnosticsResponse:
    """Return a freshly probed host-native diagnostics snapshot."""
    return diagnostics_service.build_snapshot(force_refresh=True)


app.include_router(github_router)
app.include_router(workspaces_router)
app.include_router(codex_router)
app.include_router(claude_router)
