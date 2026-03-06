"""Business logic for entity reviews."""

from uuid import UUID

from fastapi import HTTPException, status

from app.models.agent import AgentStatus
from app.models.review import ReviewEntityType
from app.models.team import TeamStatus
from app.models.user import User
from app.repositories.agent import AgentRepository
from app.repositories.review import ReviewRepository
from app.repositories.team import TeamRepository
from app.schemas.review import ReviewCreate, ReviewListResponse, ReviewRead


class ReviewService:
    """Use-case orchestration for reviews."""

    def __init__(
        self,
        review_repository: ReviewRepository,
        agent_repository: AgentRepository,
        team_repository: TeamRepository,
    ) -> None:
        self.review_repository = review_repository
        self.agent_repository = agent_repository
        self.team_repository = team_repository

    def list_agent_reviews(self, *, slug: str, limit: int, offset: int) -> ReviewListResponse:
        """Return published agent reviews."""
        entity_id = self._resolve_agent_id(slug)
        return self._list_entity_reviews(
            entity_type=ReviewEntityType.AGENT,
            entity_id=entity_id,
            limit=limit,
            offset=offset,
        )

    def create_agent_review(
        self,
        *,
        slug: str,
        payload: ReviewCreate,
        current_user: User,
    ) -> ReviewRead:
        """Create review for published agent."""
        entity_id = self._resolve_agent_id(slug)
        return self._create_entity_review(
            entity_type=ReviewEntityType.AGENT,
            entity_id=entity_id,
            payload=payload,
            current_user=current_user,
        )

    def list_team_reviews(self, *, slug: str, limit: int, offset: int) -> ReviewListResponse:
        """Return published team reviews."""
        entity_id = self._resolve_team_id(slug)
        return self._list_entity_reviews(
            entity_type=ReviewEntityType.TEAM,
            entity_id=entity_id,
            limit=limit,
            offset=offset,
        )

    def create_team_review(
        self,
        *,
        slug: str,
        payload: ReviewCreate,
        current_user: User,
    ) -> ReviewRead:
        """Create review for published team."""
        entity_id = self._resolve_team_id(slug)
        return self._create_entity_review(
            entity_type=ReviewEntityType.TEAM,
            entity_id=entity_id,
            payload=payload,
            current_user=current_user,
        )

    def _create_entity_review(
        self,
        *,
        entity_type: ReviewEntityType,
        entity_id: UUID,
        payload: ReviewCreate,
        current_user: User,
    ) -> ReviewRead:
        """Create single review if user has no prior review for entity."""
        existing = self.review_repository.get_by_user_entity(
            user_id=current_user.id,
            entity_type=entity_type.value,
            entity_id=entity_id,
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User has already reviewed this entity.",
            )

        review = self.review_repository.create(
            user_id=current_user.id,
            entity_type=entity_type.value,
            entity_id=entity_id,
            payload=payload,
        )
        return ReviewRead(
            id=review.id,
            user_id=review.user_id,
            user_display_name=current_user.display_name,
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

    def _list_entity_reviews(
        self,
        *,
        entity_type: ReviewEntityType,
        entity_id: UUID,
        limit: int,
        offset: int,
    ) -> ReviewListResponse:
        """Return paginated reviews for an entity."""
        items, total = self.review_repository.list_for_entity(
            entity_type=entity_type.value,
            entity_id=entity_id,
            limit=limit,
            offset=offset,
        )
        return ReviewListResponse(items=items, total=total, limit=limit, offset=offset)

    def _resolve_agent_id(self, slug: str) -> UUID:
        """Resolve published agent id or raise 404."""
        entity = self.agent_repository.get_by_slug(slug)
        if entity is None or entity.status != AgentStatus.PUBLISHED.value:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")
        return entity.id

    def _resolve_team_id(self, slug: str) -> UUID:
        """Resolve published team id or raise 404."""
        entity = self.team_repository.get_by_slug(slug)
        if entity is None or entity.status != TeamStatus.PUBLISHED.value:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found.")
        return entity.id
