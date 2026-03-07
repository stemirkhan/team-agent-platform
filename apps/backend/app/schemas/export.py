"""Schemas for export API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.export_job import ExportEntityType, ExportStatus, RuntimeTarget


class ExportCreate(BaseModel):
    """Payload for scheduling export."""

    runtime_target: RuntimeTarget


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
