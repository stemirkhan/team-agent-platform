"""Authentication use-cases for register/login/current-user."""

from fastapi import HTTPException, status

from app.core.config import Settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.models.user import UserRole
from app.repositories.platform_settings import PlatformSettingsRepository
from app.repositories.user import UserRepository
from app.schemas.auth import AuthLoginRequest, AuthRegisterRequest
from app.schemas.user import UserCreateInternal


class AuthService:
    """Application-level auth service."""

    def __init__(
        self,
        user_repository: UserRepository,
        platform_settings_repository: PlatformSettingsRepository,
        settings: Settings,
    ) -> None:
        self.user_repository = user_repository
        self.platform_settings_repository = platform_settings_repository
        self.settings = settings

    def register(self, payload: AuthRegisterRequest) -> tuple[User, str]:
        """Create account and issue JWT token."""
        owner = self.user_repository.get_owner()
        allow_open_registration = (
            self.platform_settings_repository.get_effective_allow_open_registration(
                default_value=self.settings.allow_open_registration
            )
        )
        if owner is not None and not allow_open_registration:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Self-registration is closed after the owner account is created.",
            )

        normalized_email = payload.email.strip().lower()
        if self.user_repository.get_by_email(normalized_email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this email already exists.",
            )

        user = self.user_repository.create(
            UserCreateInternal(
                email=normalized_email,
                password_hash=hash_password(payload.password),
                display_name=payload.display_name.strip(),
                role=UserRole.ADMIN if owner is None else UserRole.USER,
            )
        )

        token = create_access_token(user_id=user.id)
        return user, token

    def login(self, payload: AuthLoginRequest) -> tuple[User, str]:
        """Validate credentials and issue JWT token."""
        normalized_email = payload.email.strip().lower()
        user = self.user_repository.get_by_email(normalized_email)
        if user is None or not verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive.",
            )

        token = create_access_token(user_id=user.id)
        return user, token

    def get_user_by_id(self, user_id):
        """Load current user or raise unauthorized."""
        user = self.user_repository.get_by_id(user_id)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials.",
            )
        return user

    def get_owner_user(self) -> User:
        """Return the effective platform owner or fail when auth bootstrap is incomplete."""
        owner = self.user_repository.get_owner()
        if owner is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Owner account is not initialized yet.",
            )
        return owner

    def ensure_operator(self, user: User) -> User:
        """Ensure the current user is allowed to access host-backed operations."""
        if user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only platform admins can use host-backed operations.",
            )
        return user
