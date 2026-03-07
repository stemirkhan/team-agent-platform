"""Schemas for agent version release API."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentVersionCreate(BaseModel):
    """Payload for creating a new agent version."""

    version: str = Field(min_length=1, max_length=32)
    changelog: str | None = Field(default=None)
    manifest_json: dict[str, Any] | None = Field(default=None)
    source_archive_url: str | None = Field(default=None, max_length=1000)
    compatibility_matrix: dict[str, Any] | None = Field(default=None)
    export_targets: list[str] | None = Field(default=None)
    install_instructions: str | None = Field(default=None)


class AgentVersionRead(BaseModel):
    """Serialized agent version payload returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    version: str
    changelog: str | None
    manifest_json: dict[str, Any] | None
    source_archive_url: str | None
    compatibility_matrix: dict[str, Any] | None
    export_targets: list[str] | None
    install_instructions: str | None
    published_at: datetime
    is_latest: bool


class AgentVersionListResponse(BaseModel):
    """Paginated list of agent versions."""

    items: list[AgentVersionRead]
    total: int
    limit: int
    offset: int
