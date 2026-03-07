"""Agent version ORM model."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AgentVersion(Base):
    """Versioned release metadata for an agent."""

    __tablename__ = "agent_versions"
    __table_args__ = (
        UniqueConstraint("agent_id", "version", name="uq_agent_versions_agent_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    changelog: Mapped[str | None] = mapped_column(Text, nullable=True)
    manifest_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    source_archive_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    compatibility_matrix: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    export_targets: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    install_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    agent: Mapped["Agent"] = relationship(back_populates="versions")


if TYPE_CHECKING:
    from app.models.agent import Agent
