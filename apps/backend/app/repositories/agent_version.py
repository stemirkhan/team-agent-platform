"""Repository layer for internal agent export profile persistence."""

from datetime import UTC, datetime
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

    def get_by_version(self, *, agent_id: UUID, version: str) -> AgentVersion | None:
        """Return one named profile row for the agent when available."""
        query = select(AgentVersion).where(
            AgentVersion.agent_id == agent_id,
            AgentVersion.version == version,
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
        return self._upsert_profile(
            agent_id=agent.id,
            version="current",
            manifest_json=manifest_json,
            source_archive_url=source_archive_url,
            compatibility_matrix=compatibility_matrix,
            export_targets=export_targets,
            install_instructions=install_instructions,
            is_latest=True,
        )

    def upsert_draft_profile(
        self,
        *,
        agent: Agent,
        manifest_json: dict | None,
        source_archive_url: str | None,
        compatibility_matrix: dict | None,
        export_targets: list[str] | None,
        install_instructions: str | None,
    ) -> AgentVersion:
        """Create or update the pending draft profile row for one agent."""
        return self._upsert_profile(
            agent_id=agent.id,
            version="draft",
            manifest_json=manifest_json,
            source_archive_url=source_archive_url,
            compatibility_matrix=compatibility_matrix,
            export_targets=export_targets,
            install_instructions=install_instructions,
            is_latest=False,
        )

    def create_draft_profile_from_current(self, *, agent: Agent) -> AgentVersion:
        """Clone the current published profile into a draft profile row."""
        current = self.get_by_version(agent_id=agent.id, version="current")
        return self._upsert_profile(
            agent_id=agent.id,
            version="draft",
            manifest_json=current.manifest_json if current else None,
            source_archive_url=current.source_archive_url if current else None,
            compatibility_matrix=current.compatibility_matrix if current else None,
            export_targets=current.export_targets if current else None,
            install_instructions=current.install_instructions if current else None,
            is_latest=False,
        )

    def promote_draft_profile(self, *, agent: Agent) -> AgentVersion:
        """Publish the pending draft profile into the current live profile slot."""
        draft = self.get_by_version(agent_id=agent.id, version="draft")
        if draft is None:
            raise ValueError("Draft agent profile does not exist.")

        current = self.get_by_version(agent_id=agent.id, version="current")
        if current is None:
            current = AgentVersion(
                agent_id=agent.id,
                version="current",
                is_latest=True,
            )
            self.session.add(current)

        current.manifest_json = draft.manifest_json
        current.source_archive_url = draft.source_archive_url
        current.compatibility_matrix = draft.compatibility_matrix
        current.export_targets = draft.export_targets
        current.install_instructions = draft.install_instructions
        current.is_latest = True
        current.published_at = datetime.now(UTC)

        self.session.add(current)
        self.session.delete(draft)
        self.session.commit()
        self.session.refresh(current)
        return current

    def delete_draft_profile(self, *, agent: Agent) -> None:
        """Remove the pending draft profile row when present."""
        draft = self.get_by_version(agent_id=agent.id, version="draft")
        if draft is None:
            return
        self.session.delete(draft)
        self.session.commit()

    def _upsert_profile(
        self,
        *,
        agent_id: UUID,
        version: str,
        manifest_json: dict | None,
        source_archive_url: str | None,
        compatibility_matrix: dict | None,
        export_targets: list[str] | None,
        install_instructions: str | None,
        is_latest: bool,
    ) -> AgentVersion:
        """Create or update one named profile row for an agent."""
        entity = self.get_by_version(agent_id=agent_id, version=version)
        if entity is None:
            entity = AgentVersion(
                agent_id=agent_id,
                version=version,
                is_latest=is_latest,
            )
            self.session.add(entity)

        entity.manifest_json = manifest_json
        entity.source_archive_url = source_archive_url
        entity.compatibility_matrix = compatibility_matrix
        entity.export_targets = export_targets
        entity.install_instructions = install_instructions
        entity.is_latest = is_latest
        if version == "current":
            entity.published_at = datetime.now(UTC)

        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity
