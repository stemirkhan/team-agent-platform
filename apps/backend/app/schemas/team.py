"""Schemas for team builder and catalog endpoints."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.team import TeamStatus


class TeamBase(BaseModel):
    """Common mutable team fields for create payloads."""

    model_config = ConfigDict(str_strip_whitespace=True)

    slug: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=2, max_length=255)
    description: str | None = Field(default=None)
    startup_prompt: str | None = Field(default=None, max_length=8000)


class TeamCreate(TeamBase):
    """Payload for creating a team."""

    status: TeamStatus = TeamStatus.DRAFT


class TeamUpdate(BaseModel):
    """Payload for updating mutable team fields."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    startup_prompt: str | None = Field(default=None, max_length=8000)


class TeamRead(TeamBase):
    """Serialized team entity."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    author_id: UUID | None
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

    model_config = ConfigDict(str_strip_whitespace=True)

    agent_slug: str = Field(min_length=2, max_length=120)
    role_name: str = Field(min_length=2, max_length=120)
    order_index: int | None = Field(default=None, ge=0)
    config_json: dict[str, Any] | None = None
    is_required: bool = True


class TeamItemUpdate(BaseModel):
    """Payload for updating an existing team item."""

    model_config = ConfigDict(str_strip_whitespace=True)

    agent_slug: str | None = Field(default=None, min_length=2, max_length=120)
    role_name: str | None = Field(default=None, min_length=2, max_length=120)
    order_index: int | None = Field(default=None, ge=0)
    config_json: dict[str, Any] | None = None
    is_required: bool | None = None


class TeamItemRead(BaseModel):
    """Serialized team item details for UI and export flows."""

    id: UUID
    team_id: UUID
    agent_slug: str
    agent_title: str
    agent_short_description: str
    role_name: str
    order_index: int
    config_json: dict[str, Any] | None
    is_required: bool


class TeamDetailsRead(TeamRead):
    """Team details with ordered item list."""

    items: list[TeamItemRead] = Field(default_factory=list)
