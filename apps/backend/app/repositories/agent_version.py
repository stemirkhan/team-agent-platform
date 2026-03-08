"""Repository layer for internal agent export profile persistence."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.agent_version import AgentVersion


class AgentVersionRepository:
    """Data access methods for internal agent export profiles."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, *, version_id: UUID) -> AgentVersion | None:
        """Find internal agent profile row by primary key."""
        query = select(AgentVersion).where(AgentVersion.id == version_id)
        return self.session.scalar(query)

    def get_latest_for_agent(self, *, agent_id: UUID) -> AgentVersion | None:
        """Return the current stored export profile for an agent when available."""
        query = (
            select(AgentVersion)
            .where(AgentVersion.agent_id == agent_id)
            .order_by(AgentVersion.is_latest.desc(), AgentVersion.published_at.desc())
            .limit(1)
        )
        return self.session.scalar(query)

    def upsert_current_profile(
        self,
        *,
        agent: Agent,
        manifest_json: dict | None,
        source_archive_url: str | None,
        compatibility_matrix: dict | None,
        export_targets: list[str] | None,
        install_instructions: str | None,
    ) -> AgentVersion:
        """Create or update the hidden current profile row for an agent."""
        entity = self.get_latest_for_agent(agent_id=agent.id)
        if entity is None:
            entity = AgentVersion(
                agent_id=agent.id,
                version="current",
                is_latest=True,
            )
            self.session.add(entity)

        entity.manifest_json = manifest_json
        entity.source_archive_url = source_archive_url
        entity.compatibility_matrix = compatibility_matrix
        entity.export_targets = export_targets
        entity.install_instructions = install_instructions
        entity.is_latest = True

        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity
