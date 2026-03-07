"""Repository layer for agent version persistence."""

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.agent_version import AgentVersion
from app.schemas.agent_version import AgentVersionCreate


class AgentVersionRepository:
    """Data access methods for agent versions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, *, agent: Agent, payload: AgentVersionCreate) -> AgentVersion:
        """Insert a new agent version and mark it as latest."""
        self.session.execute(
            update(AgentVersion)
            .where(AgentVersion.agent_id == agent.id)
            .where(AgentVersion.is_latest.is_(True))
            .values(is_latest=False)
        )

        entity = AgentVersion(
            agent_id=agent.id,
            version=payload.version,
            changelog=payload.changelog,
            manifest_json=payload.manifest_json,
            source_archive_url=payload.source_archive_url,
            compatibility_matrix=payload.compatibility_matrix,
            export_targets=payload.export_targets,
            install_instructions=payload.install_instructions,
            is_latest=True,
        )
        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def list_for_agent(
        self,
        *,
        agent_id: UUID,
        limit: int,
        offset: int,
    ) -> tuple[list[AgentVersion], int]:
        """Return paginated versions for an agent."""
        query = (
            select(AgentVersion)
            .where(AgentVersion.agent_id == agent_id)
            .order_by(AgentVersion.published_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_query = select(func.count(AgentVersion.id)).where(AgentVersion.agent_id == agent_id)

        items = list(self.session.scalars(query).all())
        total = int(self.session.scalar(count_query) or 0)
        return items, total

    def get_by_agent_version(self, *, agent_id: UUID, version: str) -> AgentVersion | None:
        """Find specific version by agent id and version string."""
        query = select(AgentVersion).where(
            AgentVersion.agent_id == agent_id,
            AgentVersion.version == version,
        )
        return self.session.scalar(query)

    def get_latest_for_agent(self, *, agent_id: UUID) -> AgentVersion | None:
        """Return latest version for agent when available."""
        query = (
            select(AgentVersion)
            .where(AgentVersion.agent_id == agent_id)
            .order_by(AgentVersion.is_latest.desc(), AgentVersion.published_at.desc())
            .limit(1)
        )
        return self.session.scalar(query)
