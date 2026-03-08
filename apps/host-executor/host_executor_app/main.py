"""Host executor FastAPI entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from host_executor_app.api.codex import router as codex_router
from host_executor_app.api.github import router as github_router
from host_executor_app.api.workspaces import router as workspaces_router
from host_executor_app.core.config import get_settings
from host_executor_app.schemas.host import HostDiagnosticsResponse
from host_executor_app.services.host_diagnostics_service import HostDiagnosticsService

settings = get_settings()
diagnostics_service = HostDiagnosticsService()

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


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Return liveness for the host executor bridge."""
    return {"status": "ok"}


@app.get("/diagnostics", response_model=HostDiagnosticsResponse)
def diagnostics() -> HostDiagnosticsResponse:
    """Return host-native tool diagnostics."""
    return diagnostics_service.build_snapshot()


app.include_router(github_router)
app.include_router(workspaces_router)
app.include_router(codex_router)
