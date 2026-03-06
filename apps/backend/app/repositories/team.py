"""Repository layer for team and team-item persistence."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.team import Team, TeamItem
from app.schemas.team import TeamCreate, TeamItemCreate, TeamItemRead


class TeamRepository:
    """Data access methods for teams and team items."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, payload: TeamCreate, *, author_id: UUID, author_name: str) -> Team:
        """Insert and return a new team."""
        entity = Team(
            **payload.model_dump(),
            author_id=author_id,
            author_name=author_name,
        )
        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def list_teams(
        self,
        *,
        limit: int,
        offset: int,
        status: str | None,
        search: str | None,
    ) -> tuple[list[Team], int]:
        """Return filtered team list with total count."""
        query = select(Team)
        count_query = select(func.count(Team.id))

        if status:
            query = query.where(Team.status == status)
            count_query = count_query.where(Team.status == status)

        if search:
            pattern = f"%{search}%"
            query = query.where(Team.title.ilike(pattern) | Team.description.ilike(pattern))
            count_query = count_query.where(
                Team.title.ilike(pattern) | Team.description.ilike(pattern)
            )

        query = query.order_by(Team.created_at.desc()).offset(offset).limit(limit)

        items = list(self.session.scalars(query).all())
        total = int(self.session.scalar(count_query) or 0)
        return items, total

    def list_by_author(
        self,
        *,
        author_id: UUID,
        limit: int,
        offset: int,
        status: str | None,
    ) -> tuple[list[Team], int]:
        """Return paginated teams owned by the given author."""
        query = select(Team).where(Team.author_id == author_id)
        count_query = select(func.count(Team.id)).where(Team.author_id == author_id)

        if status:
            query = query.where(Team.status == status)
            count_query = count_query.where(Team.status == status)

        query = query.order_by(Team.created_at.desc()).offset(offset).limit(limit)

        items = list(self.session.scalars(query).all())
        total = int(self.session.scalar(count_query) or 0)
        return items, total

    def get_by_slug(self, slug: str) -> Team | None:
        """Find a team by slug."""
        return self.session.scalar(select(Team).where(Team.slug == slug))

    def update_status(self, team: Team, status: str) -> Team:
        """Persist status transition for a team."""
        team.status = status
        self.session.add(team)
        self.session.commit()
        self.session.refresh(team)
        return team

    def create_item(self, *, team: Team, agent: Agent, payload: TeamItemCreate) -> TeamItem:
        """Add an agent item into the given team."""
        order_index = payload.order_index
        if order_index is None:
            order_index = self._next_order_index(team.id)

        entity = TeamItem(
            team_id=team.id,
            agent_id=agent.id,
            role_name=payload.role_name,
            order_index=order_index,
            config_json=payload.config_json,
            is_required=payload.is_required,
        )
        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def list_items(self, team_id: UUID) -> list[TeamItemRead]:
        """Return ordered team items with agent slugs for UI."""
        query = (
            select(TeamItem, Agent.slug)
            .join(Agent, Agent.id == TeamItem.agent_id)
            .where(TeamItem.team_id == team_id)
            .order_by(TeamItem.order_index.asc())
        )

        rows = self.session.execute(query).all()
        return [
            TeamItemRead(
                id=item.id,
                team_id=item.team_id,
                agent_id=item.agent_id,
                agent_slug=agent_slug,
                role_name=item.role_name,
                order_index=item.order_index,
                config_json=item.config_json,
                is_required=item.is_required,
            )
            for item, agent_slug in rows
        ]

    def _next_order_index(self, team_id: UUID) -> int:
        """Return next sequential index for team item ordering."""
        max_order = self.session.scalar(
            select(func.max(TeamItem.order_index)).where(TeamItem.team_id == team_id)
        )
        return 0 if max_order is None else int(max_order) + 1
