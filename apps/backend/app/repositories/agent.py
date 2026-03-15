"""Repository layer for working with agent records."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.schemas.agent import AgentCreate


class AgentRepository:
    """Data access methods for published agents."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, payload: AgentCreate, *, author_id: UUID, author_name: str) -> Agent:
        """Insert a new agent and return persisted entity."""
        entity = Agent(
            **payload.model_dump(),
            author_id=author_id,
            author_name=author_name,
        )
        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def list(
        self,
        *,
        limit: int,
        offset: int,
        status: str | None,
        category: str | None,
        search: str | None,
    ) -> tuple[list[Agent], int]:
        """Return filtered and paginated list of agents with total count."""
        query = select(Agent)
        count_query = select(func.count(Agent.id))

        if status:
            query = query.where(Agent.status == status)
            count_query = count_query.where(Agent.status == status)

        if category:
            query = query.where(Agent.category == category)
            count_query = count_query.where(Agent.category == category)

        if search:
            pattern = f"%{search}%"
            query = query.where(Agent.title.ilike(pattern) | Agent.short_description.ilike(pattern))
            count_query = count_query.where(
                Agent.title.ilike(pattern) | Agent.short_description.ilike(pattern)
            )

        query = query.order_by(Agent.created_at.desc()).offset(offset).limit(limit)

        items = list(self.session.scalars(query).all())
        total = int(self.session.scalar(count_query) or 0)
        return items, total

    def get_by_slug(self, slug: str) -> Agent | None:
        """Find agent by slug."""
        query = select(Agent).where(Agent.slug == slug)
        return self.session.scalar(query)

    def update_status(self, agent: Agent, status: str) -> Agent:
        """Persist status transition for an existing agent."""
        agent.status = status
        self.session.add(agent)
        self.session.commit()
        self.session.refresh(agent)
        return agent

    def update(self, agent: Agent, *, fields: dict[str, object]) -> Agent:
        """Persist mutable agent field changes."""
        for key, value in fields.items():
            setattr(agent, key, value)
        self.session.add(agent)
        self.session.commit()
        self.session.refresh(agent)
        return agent
