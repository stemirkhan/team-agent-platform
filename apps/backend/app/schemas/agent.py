"""Schemas for agent catalog and publishing API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.agent import AgentStatus, VerificationStatus


class AgentBase(BaseModel):
    """Common mutable agent fields for create payloads."""

    slug: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=2, max_length=255)
    short_description: str = Field(min_length=10, max_length=500)
    full_description: str | None = Field(default=None)
    category: str | None = Field(default=None, max_length=120)


class AgentCreate(AgentBase):
    """Payload for creating a draft agent."""

    status: AgentStatus = AgentStatus.DRAFT


class AgentUpdateStatus(BaseModel):
    """Payload for status transitions."""

    status: AgentStatus


class AgentRead(AgentBase):
    """Serialized agent entity returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    author_name: str
    status: AgentStatus
    verification_status: VerificationStatus
    created_at: datetime
    updated_at: datetime


class AgentListResponse(BaseModel):
    """Paginated list of agents."""

    items: list[AgentRead]
    total: int
    limit: int
    offset: int
