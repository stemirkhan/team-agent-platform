"""Repository layer for review persistence and listing."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.review import Review
from app.models.user import User
from app.schemas.review import ReviewCreate, ReviewRead


class ReviewRepository:
    """Data access methods for reviews."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        user_id: UUID,
        entity_type: str,
        entity_id: UUID,
        payload: ReviewCreate,
    ) -> Review:
        """Create and return review entity."""
        entity = Review(
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            **payload.model_dump(),
        )
        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def get_by_user_entity(
        self,
        *,
        user_id: UUID,
        entity_type: str,
        entity_id: UUID,
    ) -> Review | None:
        """Find existing review by user and entity."""
        query = select(Review).where(
            Review.user_id == user_id,
            Review.entity_type == entity_type,
            Review.entity_id == entity_id,
        )
        return self.session.scalar(query)

    def list_for_entity(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
        limit: int,
        offset: int,
    ) -> tuple[list[ReviewRead], int]:
        """Return paginated reviews for target entity with reviewer names."""
        query = (
            select(Review, User.display_name)
            .join(User, User.id == Review.user_id)
            .where(
                Review.entity_type == entity_type,
                Review.entity_id == entity_id,
            )
            .order_by(Review.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = self.session.execute(query).all()

        count_query = select(func.count(Review.id)).where(
            Review.entity_type == entity_type,
            Review.entity_id == entity_id,
        )
        total = int(self.session.scalar(count_query) or 0)

        items = [
            ReviewRead(
                id=review.id,
                user_id=review.user_id,
                user_display_name=display_name,
                entity_type=review.entity_type,
                entity_id=review.entity_id,
                rating=review.rating,
                text=review.text,
                works_as_expected=review.works_as_expected,
                outdated_flag=review.outdated_flag,
                unsafe_flag=review.unsafe_flag,
                created_at=review.created_at,
                updated_at=review.updated_at,
            )
            for review, display_name in rows
        ]
        return items, total
