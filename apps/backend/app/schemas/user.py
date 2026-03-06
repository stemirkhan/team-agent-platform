"""Schemas related to user accounts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import UserRole


class UserRead(BaseModel):
    """Public serialized user representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserCreateInternal(BaseModel):
    """Internal payload for user creation."""

    email: str
    password_hash: str
    display_name: str = Field(min_length=2, max_length=120)
    role: UserRole = UserRole.USER
