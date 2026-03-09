"""Schemas for run lifecycle endpoints."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.run import RunEventType, RunStatus
from app.schemas.export import CodexExportOptions


class RunCreate(BaseModel):
    """Payload for preparing a new run over a repository target."""

    model_config = ConfigDict(str_strip_whitespace=True)

    team_slug: str = Field(min_length=2, max_length=120)
    repo_owner: str = Field(min_length=1, max_length=255)
    repo_name: str = Field(min_length=1, max_length=255)
    base_branch: str | None = Field(default=None, min_length=1, max_length=255)
    issue_number: int | None = Field(default=None, ge=1)
    task_text: str | None = Field(default=None, min_length=1, max_length=20_000)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    summary: str | None = Field(default=None, max_length=4_000)
    codex: CodexExportOptions | None = None

    @model_validator(mode="after")
    def validate_task_source(self) -> "RunCreate":
        """Require either issue context or manual task text."""
        if self.issue_number is None and not self.task_text:
            raise ValueError("Either issue_number or task_text must be provided.")
        return self


RunReportPhaseKey = Literal["preparation", "setup", "codex", "checks", "git_pr"]
RunReportPhaseStatus = Literal[
    "not_started",
    "running",
    "completed",
    "failed",
    "cancelled",
    "not_available",
]


class RunReportCommandRead(BaseModel):
    """One command execution record for setup/check phases."""

    command: str
    exit_code: int
    succeeded: bool
    output: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class RunReportPhaseRead(BaseModel):
    """Structured phase-level snapshot for one run."""

    key: RunReportPhaseKey
    order: int
    status: RunReportPhaseStatus
    description: str | None = None
    first_event_at: datetime | None = None
    last_event_at: datetime | None = None
    commands: list[RunReportCommandRead] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class RunReportRead(BaseModel):
    """Top-level structured report grouped by execution phases."""

    phases: list[RunReportPhaseRead] = Field(default_factory=list)


class RunRead(BaseModel):
    """Serialized run payload."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    team_id: UUID | None = None
    team_slug: str
    team_title: str
    runtime_target: Literal["codex"]
    repo_owner: str
    repo_name: str
    repo_full_name: str
    base_branch: str
    working_branch: str | None = None
    issue_number: int | None = None
    issue_title: str | None = None
    issue_url: str | None = None
    title: str
    summary: str | None = None
    task_text: str | None = None
    runtime_config_json: dict[str, Any] | None = None
    workspace_id: str | None = None
    workspace_path: str | None = None
    repo_path: str | None = None
    status: RunStatus
    error_message: str | None = None
    pr_url: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    run_report: RunReportRead | None = None


class RunListResponse(BaseModel):
    """Paginated list of runs."""

    items: list[RunRead]
    total: int
    limit: int
    offset: int


class RunEventRead(BaseModel):
    """Serialized run event payload."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    event_type: RunEventType
    payload_json: dict[str, Any] | None = None
    created_at: datetime


class RunEventListResponse(BaseModel):
    """Ordered run-event list."""

    items: list[RunEventRead]
    total: int
