"""Run and run-event ORM models."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class RunStatus(StrEnum):
    """Execution lifecycle state for one repo task run."""

    QUEUED = "queued"
    PREPARING = "preparing"
    CLONING_REPO = "cloning_repo"
    MATERIALIZING_TEAM = "materializing_team"
    RUNNING_SETUP = "running_setup"
    STARTING_CODEX = "starting_codex"
    RUNNING = "running"
    RUNNING_CHECKS = "running_checks"
    COMMITTING = "committing"
    PUSHING = "pushing"
    CREATING_PR = "creating_pr"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunEventType(StrEnum):
    """Stored run-event kinds."""

    STATUS = "status"
    ERROR = "error"
    NOTE = "note"


class Run(Base):
    """One Codex execution session over a GitHub repository."""

    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("teams.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    team_slug: Mapped[str] = mapped_column(String(120), nullable=False)
    team_title: Mapped[str] = mapped_column(String(255), nullable=False)
    runtime_target: Mapped[str] = mapped_column(String(32), nullable=False, default="codex")
    repo_owner: Mapped[str] = mapped_column(String(255), nullable=False)
    repo_name: Mapped[str] = mapped_column(String(255), nullable=False)
    repo_full_name: Mapped[str] = mapped_column(String(511), nullable=False)
    base_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    working_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    issue_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    issue_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    issue_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    runtime_config_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    workspace_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    workspace_path: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    repo_path: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=RunStatus.QUEUED.value)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    pr_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    events: Mapped[list["RunEvent"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class RunEvent(Base):
    """Persistent non-terminal event emitted during run orchestration."""

    __tablename__ = "run_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    run: Mapped[Run] = relationship(back_populates="events")


if TYPE_CHECKING:
    pass
