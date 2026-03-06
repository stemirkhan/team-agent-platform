"""Authentication endpoints for MVP."""

from fastapi import APIRouter, Depends, status

from app.api.deps import get_auth_service
from app.schemas.auth import AuthLoginRequest, AuthRegisterRequest, AuthTokenResponse
from app.schemas.user import UserRead
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: AuthRegisterRequest,
    service: AuthService = Depends(get_auth_service),
) -> AuthTokenResponse:
    """Create user account and return access token."""
    user, token = service.register(payload)
    return AuthTokenResponse(access_token=token, user=UserRead.model_validate(user))


@router.post("/login", response_model=AuthTokenResponse)
def login(
    payload: AuthLoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> AuthTokenResponse:
    """Authenticate user and return access token."""
    user, token = service.login(payload)
    return AuthTokenResponse(access_token=token, user=UserRead.model_validate(user))
