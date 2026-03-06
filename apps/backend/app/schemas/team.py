"""Schemas for team builder and catalog endpoints."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.team import TeamStatus


class TeamBase(BaseModel):
    """Common mutable team fields for create payloads."""

    slug: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=2, max_length=255)
    description: str | None = Field(default=None)


class TeamCreate(TeamBase):
    """Payload for creating a team."""

    status: TeamStatus = TeamStatus.DRAFT


class TeamRead(TeamBase):
    """Serialized team entity."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    author_name: str
    status: TeamStatus
    created_at: datetime
    updated_at: datetime


class TeamListResponse(BaseModel):
    """Paginated list of teams."""

    items: list[TeamRead]
    total: int
    limit: int
    offset: int


class TeamItemCreate(BaseModel):
    """Payload for adding an agent to a team."""

    agent_slug: str = Field(min_length=2, max_length=120)
    role_name: str = Field(min_length=2, max_length=120)
    order_index: int | None = Field(default=None, ge=0)
    config_json: dict[str, Any] | None = None
    is_required: bool = True


class TeamItemRead(BaseModel):
    """Serialized team item with agent slug for UI."""

    id: UUID
    team_id: UUID
    agent_id: UUID
    agent_slug: str
    role_name: str
    order_index: int
    config_json: dict[str, Any] | None
    is_required: bool


class TeamDetailsRead(TeamRead):
    """Team details with ordered item list."""

    items: list[TeamItemRead] = []
