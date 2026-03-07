"""Application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.downloads import router as downloads_router
from app.api.router import router as api_router
from app.core.config import get_settings
from app.schemas.health import HealthResponse

settings = get_settings()

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

app.include_router(api_router)
app.include_router(downloads_router)


@app.get("/healthz", response_model=HealthResponse, tags=["health"])
def root_health() -> HealthResponse:
    """Root-level health endpoint for container probes."""
    return HealthResponse()
