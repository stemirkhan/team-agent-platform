"""Schemas for agent catalog and publishing API."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.agent import AgentStatus, VerificationStatus
from app.schemas.agent_version import AgentMarkdownFilePayload, AgentSkillPayload
from app.utils.agent_assets import normalize_markdown_file_records, normalize_skill_records


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


class AgentUpdate(BaseModel):
    """Payload for updating agent metadata and current export profile."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=2, max_length=255)
    short_description: str | None = Field(default=None, min_length=10, max_length=500)
    full_description: str | None = Field(default=None)
    category: str | None = Field(default=None, max_length=120)
    manifest_json: dict[str, Any] | None = Field(default=None)
    source_archive_url: str | None = Field(default=None, max_length=1000)
    compatibility_matrix: dict[str, Any] | None = Field(default=None)
    export_targets: list[str] | None = Field(default=None)
    install_instructions: str | None = Field(default=None)
    skills: list[AgentSkillPayload] | None = Field(default=None)
    markdown_files: list[AgentMarkdownFilePayload] | None = Field(default=None)


class AgentRead(AgentBase):
    """Serialized agent entity returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    author_name: str
    status: AgentStatus
    verification_status: VerificationStatus
    created_at: datetime
    updated_at: datetime
    manifest_json: dict[str, Any] | None = None
    source_archive_url: str | None = None
    compatibility_matrix: dict[str, Any] | None = None
    export_targets: list[str] | None = None
    install_instructions: str | None = None

    @computed_field(return_type=list[AgentSkillPayload])
    @property
    def skills(self) -> list[AgentSkillPayload]:
        """Expose normalized agent skills from current manifest."""
        records = normalize_skill_records(
            self.manifest_json.get("skills") if isinstance(self.manifest_json, dict) else None,
            strict=False,
        )
        return [AgentSkillPayload.model_validate(record) for record in records]

    @computed_field(return_type=list[AgentMarkdownFilePayload])
    @property
    def markdown_files(self) -> list[AgentMarkdownFilePayload]:
        """Expose normalized agent markdown files from current manifest."""
        records = normalize_markdown_file_records(
            self.manifest_json.get("markdown_files")
            if isinstance(self.manifest_json, dict)
            else None,
            strict=False,
        )
        return [AgentMarkdownFilePayload.model_validate(record) for record in records]


class AgentListResponse(BaseModel):
    """Paginated list of agents."""

    items: list[AgentRead]
    total: int
    limit: int
    offset: int
