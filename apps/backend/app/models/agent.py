"""Agent ORM model for published subagents."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.agent_version import AgentVersion


class AgentStatus(StrEnum):
    """Publishing state of an agent."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    HIDDEN = "hidden"


class VerificationStatus(StrEnum):
    """Verification level assigned by validation/moderation."""

    NONE = "none"
    VALIDATED = "validated"
    VERIFIED = "verified"


class Agent(Base):
    """Published agent entity."""

    __tablename__ = "agents"
    __table_args__ = (UniqueConstraint("slug", name="uq_agents_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    short_description: Mapped[str] = mapped_column(String(500), nullable=False)
    full_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    author_name: Mapped[str] = mapped_column(String(120), nullable=False, default="system")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=AgentStatus.DRAFT.value)
    verification_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=VerificationStatus.NONE.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    versions: Mapped[list["AgentVersion"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def current_version(self) -> "AgentVersion | None":
        """Return the internal current export profile for this agent."""
        if not self.versions:
            return None
        return sorted(
            self.versions,
            key=lambda version: (version.is_latest, version.published_at),
            reverse=True,
        )[0]

    @property
    def manifest_json(self) -> dict[str, Any] | None:
        """Expose current manifest data on the agent entity."""
        return self.current_version.manifest_json if self.current_version else None

    @property
    def source_archive_url(self) -> str | None:
        """Expose current source archive URL on the agent entity."""
        return self.current_version.source_archive_url if self.current_version else None

    @property
    def compatibility_matrix(self) -> dict[str, Any] | None:
        """Expose current compatibility matrix on the agent entity."""
        return self.current_version.compatibility_matrix if self.current_version else None

    @property
    def export_targets(self) -> list[str] | None:
        """Expose current export targets on the agent entity."""
        return self.current_version.export_targets if self.current_version else None

    @property
    def install_instructions(self) -> str | None:
        """Expose current install instructions on the agent entity."""
        return self.current_version.install_instructions if self.current_version else None
