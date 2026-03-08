"""Repository layer for team and team-item persistence."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.agent_version import AgentVersion
from app.models.team import Team, TeamItem
from app.schemas.team import TeamCreate, TeamItemCreate, TeamItemRead, TeamUpdate


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

    def update(self, team: Team, payload: TeamUpdate) -> Team:
        """Persist mutable team field changes."""
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(team, field, value)
        self.session.add(team)
        self.session.commit()
        self.session.refresh(team)
        return team

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

    def create_item(
        self,
        *,
        team: Team,
        agent_version: AgentVersion,
        payload: TeamItemCreate,
        order_index: int,
    ) -> TeamItem:
        """Add the current agent export profile to the given team."""
        entity = TeamItem(
            team_id=team.id,
            agent_version_id=agent_version.id,
            role_name=payload.role_name,
            order_index=order_index,
            config_json=payload.config_json,
            is_required=payload.is_required,
        )
        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def get_item_by_id(self, *, team_id: UUID, item_id: UUID) -> TeamItem | None:
        """Find one team item scoped to the parent team."""
        query = select(TeamItem).where(
            TeamItem.team_id == team_id,
            TeamItem.id == item_id,
        )
        return self.session.scalar(query)

    def list_item_entities(self, team_id: UUID) -> list[TeamItem]:
        """Return mutable team item ORM entities in display order."""
        query = (
            select(TeamItem)
            .where(TeamItem.team_id == team_id)
            .order_by(TeamItem.order_index.asc(), TeamItem.id.asc())
        )
        return list(self.session.scalars(query).all())

    def save_items(self, items: list[TeamItem]) -> None:
        """Persist item updates in one transaction."""
        for item in items:
            self.session.add(item)
        self.session.commit()

    def delete_item(self, item: TeamItem) -> None:
        """Delete one team item."""
        self.session.delete(item)
        self.session.commit()

    def list_items(self, team_id: UUID) -> list[TeamItemRead]:
        """Return ordered team items with agent metadata for UI."""
        query = (
            select(
                TeamItem,
                Agent.slug,
                Agent.title,
                Agent.short_description,
            )
            .join(AgentVersion, AgentVersion.id == TeamItem.agent_version_id)
            .join(Agent, Agent.id == AgentVersion.agent_id)
            .where(TeamItem.team_id == team_id)
            .order_by(TeamItem.order_index.asc(), TeamItem.id.asc())
        )

        rows = self.session.execute(query).all()
        return [
            TeamItemRead(
                id=item.id,
                team_id=item.team_id,
                agent_slug=agent_slug,
                agent_title=agent_title,
                agent_short_description=agent_short_description,
                role_name=item.role_name,
                order_index=item.order_index,
                config_json=item.config_json,
                is_required=item.is_required,
            )
            for item, agent_slug, agent_title, agent_short_description in rows
        ]
