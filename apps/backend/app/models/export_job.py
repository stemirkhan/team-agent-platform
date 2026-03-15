"""Export job ORM model."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ExportEntityType(StrEnum):
    """Supported export entity types."""

    AGENT = "agent"
    TEAM = "team"


class RuntimeTarget(StrEnum):
    """Supported runtime targets for export."""

    CODEX = "codex"
    CLAUDE_CODE = "claude_code"


class ExportStatus(StrEnum):
    """Lifecycle status of export job."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class ExportJob(Base):
    """Single export request tracked in storage."""

    __tablename__ = "exports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    runtime_target: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ExportStatus.PENDING.value,
    )
    result_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
