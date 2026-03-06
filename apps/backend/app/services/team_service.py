"""Business logic for team catalog and team builder operations."""

from uuid import UUID

from fastapi import HTTPException, status

from app.models.agent import AgentStatus
from app.models.team import TeamStatus
from app.models.user import User
from app.repositories.agent import AgentRepository
from app.repositories.team import TeamRepository
from app.schemas.team import TeamCreate, TeamDetailsRead, TeamItemCreate, TeamListResponse, TeamRead


class TeamService:
    """Use-case orchestration for teams."""

    def __init__(self, team_repository: TeamRepository, agent_repository: AgentRepository) -> None:
        self.team_repository = team_repository
        self.agent_repository = agent_repository

    def create_team(self, payload: TeamCreate, current_user: User):
        """Create a team if slug is unique."""
        existing = self.team_repository.get_by_slug(payload.slug)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Team with the provided slug already exists.",
            )
        return self.team_repository.create(
            payload,
            author_id=current_user.id,
            author_name=current_user.display_name,
        )

    def list_teams(
        self,
        *,
        limit: int,
        offset: int,
        status_filter: TeamStatus | None,
        search: str | None,
    ) -> TeamListResponse:
        """Return paginated team list."""
        status_value = status_filter.value if status_filter else None
        items, total = self.team_repository.list_teams(
            limit=limit,
            offset=offset,
            status=status_value,
            search=search,
        )
        return TeamListResponse(items=items, total=total, limit=limit, offset=offset)

    def list_my_teams(
        self,
        *,
        current_user: User,
        limit: int,
        offset: int,
        status_filter: TeamStatus | None,
    ) -> TeamListResponse:
        """Return paginated list of teams owned by current user."""
        status_value = status_filter.value if status_filter else None
        items, total = self.team_repository.list_by_author(
            author_id=current_user.id,
            limit=limit,
            offset=offset,
            status=status_value,
        )
        return TeamListResponse(items=items, total=total, limit=limit, offset=offset)

    def get_team(self, slug: str) -> TeamDetailsRead:
        """Return team details with item list."""
        team = self._get_team_entity(slug)
        items = self.team_repository.list_items(team.id)
        payload = TeamRead.model_validate(team).model_dump()
        return TeamDetailsRead(**payload, items=items)

    def add_item(self, slug: str, payload: TeamItemCreate, current_user: User) -> TeamDetailsRead:
        """Add a published agent into a team."""
        team = self._get_team_entity(slug)
        self._ensure_owner(team.author_id, current_user.id)
        agent = self.agent_repository.get_by_slug(payload.agent_slug)
        if agent is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")

        if agent.status != AgentStatus.PUBLISHED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only published agents can be added to a team.",
            )

        self.team_repository.create_item(team=team, agent=agent, payload=payload)
        return self.get_team(slug)

    def publish_team(self, slug: str, current_user: User):
        """Move team to published state."""
        team = self._get_team_entity(slug)
        self._ensure_owner(team.author_id, current_user.id)
        return self.team_repository.update_status(team, TeamStatus.PUBLISHED.value)

    def _get_team_entity(self, slug: str):
        """Load team by slug or raise 404."""
        entity = self.team_repository.get_by_slug(slug)
        if entity is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found.")
        return entity

    @staticmethod
    def _ensure_owner(author_id: UUID | None, actor_user_id: UUID) -> None:
        """Ensure mutating action is made by the resource owner."""
        if author_id != actor_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the author can modify this team.",
            )
