"""Application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.downloads import router as downloads_router
from app.api.router import router as api_router
from app.core.db import SessionLocal
from app.core.config import get_settings
from app.schemas.health import HealthResponse
from app.services.run_reconciler import RunReconciler

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start and stop background services owned by the backend process."""
    reconciler: RunReconciler | None = None
    if settings.run_reconciler_enabled:
        reconciler = RunReconciler(session_factory=SessionLocal, settings=settings)
        app.state.run_reconciler = reconciler
        reconciler.start()
    try:
        yield
    finally:
        if reconciler is not None:
            reconciler.stop()


app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(downloads_router)


@app.get("/healthz", response_model=HealthResponse, tags=["health"])
def root_health() -> HealthResponse:
    """Root-level health endpoint for container probes."""
    return HealthResponse()
