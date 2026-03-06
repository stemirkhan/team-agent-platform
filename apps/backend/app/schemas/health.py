"""Schemas for health-check endpoints."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """API health response payload."""

    status: str = "ok"
