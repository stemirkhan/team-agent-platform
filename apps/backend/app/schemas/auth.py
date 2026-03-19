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


class BootstrapStatusRead(BaseModel):
    """Public first-run setup status for the platform."""

    setup_required: bool
    allow_open_registration: bool


class BootstrapSetupRequest(BaseModel):
    """Payload for first-run platform setup."""

    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=2, max_length=120)
    allow_open_registration: bool = False
    seed_starter_team: bool = False


class BootstrapSetupResponse(AuthTokenResponse):
    """Bootstrap response with the new admin session and setup summary."""

    bootstrap_status: BootstrapStatusRead
    seeded_team_slug: str | None = None
