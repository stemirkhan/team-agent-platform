"""Schemas for review creation and listing."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.review import ReviewEntityType


class ReviewCreate(BaseModel):
    """Payload for creating review."""

    rating: int = Field(ge=1, le=5)
    text: str | None = Field(default=None, max_length=4000)
    works_as_expected: bool = True
    outdated_flag: bool = False
    unsafe_flag: bool = False


class ReviewRead(BaseModel):
    """Serialized review payload."""

    id: UUID
    user_id: UUID
    user_display_name: str
    entity_type: ReviewEntityType
    entity_id: UUID
    rating: int
    text: str | None
    works_as_expected: bool
    outdated_flag: bool
    unsafe_flag: bool
    created_at: datetime
    updated_at: datetime


class ReviewListResponse(BaseModel):
    """Paginated review list."""

    items: list[ReviewRead]
    total: int
    limit: int
    offset: int
