"""Authentication endpoints for MVP."""

from fastapi import APIRouter, Depends, status

from app.api.deps import get_auth_service, get_bootstrap_service
from app.schemas.auth import (
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthTokenResponse,
    BootstrapSetupRequest,
    BootstrapSetupResponse,
    BootstrapStatusRead,
)
from app.schemas.user import UserRead
from app.services.auth_service import AuthService
from app.services.bootstrap_service import BootstrapService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/bootstrap", response_model=BootstrapStatusRead)
def get_bootstrap_status(
    service: BootstrapService = Depends(get_bootstrap_service),
) -> BootstrapStatusRead:
    """Return whether first-run platform setup is still required."""
    return service.get_status()


@router.post("/bootstrap", response_model=BootstrapSetupResponse, status_code=status.HTTP_201_CREATED)
def bootstrap_platform(
    payload: BootstrapSetupRequest,
    service: BootstrapService = Depends(get_bootstrap_service),
) -> BootstrapSetupResponse:
    """Create the first admin account and optional starter catalog."""
    return service.bootstrap(payload)


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
