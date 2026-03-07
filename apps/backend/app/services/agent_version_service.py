"""Business logic for agent version management."""

from uuid import UUID

from fastapi import HTTPException, status

from app.models.user import User
from app.repositories.agent import AgentRepository
from app.repositories.agent_version import AgentVersionRepository
from app.schemas.agent_version import AgentVersionCreate, AgentVersionListResponse


class AgentVersionService:
    """Use-case orchestration for agent versions."""

    def __init__(
        self,
        agent_repository: AgentRepository,
        agent_version_repository: AgentVersionRepository,
    ) -> None:
        self.agent_repository = agent_repository
        self.agent_version_repository = agent_version_repository

    def create_version(self, *, slug: str, payload: AgentVersionCreate, current_user: User):
        """Create new agent version for the resource owner."""
        agent = self._get_agent(slug)
        self._ensure_owner(agent.author_id, current_user.id)
        existing = self.agent_version_repository.get_by_agent_version(
            agent_id=agent.id,
            version=payload.version,
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Agent version already exists.",
            )
        return self.agent_version_repository.create(agent=agent, payload=payload)

    def list_versions(self, *, slug: str, limit: int, offset: int) -> AgentVersionListResponse:
        """Return paginated version list for an agent."""
        agent = self._get_agent(slug)
        items, total = self.agent_version_repository.list_for_agent(
            agent_id=agent.id,
            limit=limit,
            offset=offset,
        )
        return AgentVersionListResponse(items=items, total=total, limit=limit, offset=offset)

    def get_version(self, *, slug: str, version: str):
        """Return agent version details by version string."""
        agent = self._get_agent(slug)
        entity = self.agent_version_repository.get_by_agent_version(
            agent_id=agent.id,
            version=version,
        )
        if entity is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent version not found.",
            )
        return entity

    def _get_agent(self, slug: str):
        """Load agent by slug or raise 404."""
        entity = self.agent_repository.get_by_slug(slug)
        if entity is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")
        return entity

    @staticmethod
    def _ensure_owner(author_id: UUID | None, actor_user_id: UUID) -> None:
        """Ensure mutating action is made by the resource owner."""
        if author_id != actor_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the author can modify this agent.",
            )
