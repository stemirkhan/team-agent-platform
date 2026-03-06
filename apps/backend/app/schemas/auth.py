"""Schemas for authentication endpoints."""

from pydantic import BaseModel, Field

from app.schemas.user import UserRead


class AuthRegisterRequest(BaseModel):
    """Registration payload."""

    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=2, max_length=120)


class AuthLoginRequest(BaseModel):
    """Login payload."""

    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=8, max_length=128)


class AuthTokenResponse(BaseModel):
    """Bearer token response with current user payload."""

    access_token: str
    token_type: str = "bearer"
    user: UserRead
