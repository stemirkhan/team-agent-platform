"""Schemas for export API."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.export_job import ExportEntityType, ExportStatus, RuntimeTarget


class CodexExportOptions(BaseModel):
    """Optional Codex parameters selected at export/download time."""

    model_config = ConfigDict(str_strip_whitespace=True)

    model: str | None = Field(default=None, min_length=1, max_length=128)
    model_reasoning_effort: Literal["low", "medium", "high", "xhigh"] | None = None
    sandbox_mode: Literal["read-only", "workspace-write", "danger-full-access"] | None = None

    def to_query_params(self) -> dict[str, str]:
        """Return non-empty options as query params."""
        params: dict[str, str] = {}
        if self.model:
            params["model"] = self.model
        if self.model_reasoning_effort:
            params["model_reasoning_effort"] = self.model_reasoning_effort
        if self.sandbox_mode:
            params["sandbox_mode"] = self.sandbox_mode
        return params


class ExportCreate(BaseModel):
    """Payload for scheduling export."""

    runtime_target: RuntimeTarget
    codex: CodexExportOptions | None = None


class ExportRead(BaseModel):
    """Serialized export job payload."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entity_type: ExportEntityType
    entity_id: UUID
    runtime_target: RuntimeTarget
    status: ExportStatus
    result_url: str | None
    error_message: str | None
    created_by: UUID
    created_at: datetime


class ExportListResponse(BaseModel):
    """Paginated list of export jobs."""

    items: list[ExportRead]
    total: int
    limit: int
    offset: int
