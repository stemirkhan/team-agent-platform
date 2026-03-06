"""Security helpers for password hashing and JWT tokens."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from jwt import PyJWTError
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    """Return hashed password value."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Validate plaintext password against hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(*, user_id: UUID) -> str:
    """Create signed JWT access token for user id."""
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> UUID | None:
    """Decode JWT and return user id if token is valid."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except PyJWTError:
        return None

    if payload.get("type") != "access":
        return None

    subject = payload.get("sub")
    if not isinstance(subject, str):
        return None

    try:
        return UUID(subject)
    except ValueError:
        return None
