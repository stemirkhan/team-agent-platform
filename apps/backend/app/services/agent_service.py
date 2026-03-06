"""Business logic for agent lifecycle and catalog queries."""

from uuid import UUID

from fastapi import HTTPException, status

from app.models.agent import AgentStatus
from app.models.user import User
from app.repositories.agent import AgentRepository
from app.schemas.agent import AgentCreate, AgentListResponse


class AgentService:
    """Use-case orchestration for marketplace agents."""

    def __init__(self, repository: AgentRepository) -> None:
        self.repository = repository

    def create_agent(self, payload: AgentCreate, current_user: User):
        """Create an agent if slug is unique."""
        existing = self.repository.get_by_slug(payload.slug)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Agent with the provided slug already exists.",
            )
        return self.repository.create(
            payload,
            author_id=current_user.id,
            author_name=current_user.display_name,
        )

    def list_agents(
        self,
        *,
        limit: int,
        offset: int,
        status_filter: AgentStatus | None,
        category: str | None,
        search: str | None,
    ) -> AgentListResponse:
        """Return paginated list of agents."""
        status_value = status_filter.value if status_filter else None
        items, total = self.repository.list(
            limit=limit,
            offset=offset,
            status=status_value,
            category=category,
            search=search,
        )
        return AgentListResponse(items=items, total=total, limit=limit, offset=offset)

    def get_agent(self, slug: str):
        """Return an agent or raise 404."""
        entity = self.repository.get_by_slug(slug)
        if entity is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")
        return entity

    def publish_agent(self, slug: str, current_user: User):
        """Move agent to published status."""
        entity = self.get_agent(slug)
        self._ensure_owner(entity.author_id, current_user.id)
        return self.repository.update_status(entity, AgentStatus.PUBLISHED.value)

    @staticmethod
    def _ensure_owner(author_id: UUID | None, actor_user_id: UUID) -> None:
        """Ensure mutating action is made by the resource owner."""
        if author_id != actor_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the author can modify this agent.",
            )
