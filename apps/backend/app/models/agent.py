"""Agent ORM model for published subagents."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


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
    """Marketplace agent entity."""

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
