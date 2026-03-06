"""Repository layer for user accounts."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserCreateInternal


class UserRepository:
    """Data access methods for user entities."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, payload: UserCreateInternal) -> User:
        """Create and return user."""
        entity = User(**payload.model_dump())
        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def get_by_email(self, email: str) -> User | None:
        """Find user by normalized email."""
        return self.session.scalar(select(User).where(User.email == email))

    def get_by_id(self, user_id: UUID) -> User | None:
        """Find user by primary key."""
        return self.session.scalar(select(User).where(User.id == user_id))
