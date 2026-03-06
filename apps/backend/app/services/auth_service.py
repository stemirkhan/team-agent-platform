"""Authentication use-cases for register/login/current-user."""

from fastapi import HTTPException, status

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import AuthLoginRequest, AuthRegisterRequest
from app.schemas.user import UserCreateInternal


class AuthService:
    """Application-level auth service."""

    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    def register(self, payload: AuthRegisterRequest) -> tuple[User, str]:
        """Create account and issue JWT token."""
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
