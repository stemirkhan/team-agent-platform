"""Repository layer for user accounts."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user import UserRole
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

    def count_users(self) -> int:
        """Return total number of stored users."""
        return int(self.session.scalar(select(func.count(User.id))) or 0)

    def get_owner(self) -> User | None:
        """Return the effective platform owner user."""
        return self.session.scalar(
            select(User)
            .where(User.is_active.is_(True))
            .where(User.role == UserRole.ADMIN.value)
            .order_by(User.created_at.asc(), User.id.asc())
        )
