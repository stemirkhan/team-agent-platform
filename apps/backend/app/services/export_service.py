"""Business logic for agent and team exports."""

from uuid import UUID

from fastapi import HTTPException, status

from app.models.agent import AgentStatus
from app.models.export_job import ExportEntityType, ExportStatus
from app.models.team import TeamStatus
from app.models.user import User
from app.repositories.agent import AgentRepository
from app.repositories.export_job import ExportJobRepository
from app.repositories.team import TeamRepository
from app.schemas.export import ExportCreate


class ExportService:
    """Use-case orchestration for export jobs."""

    def __init__(
        self,
        export_repository: ExportJobRepository,
        agent_repository: AgentRepository,
        team_repository: TeamRepository,
    ) -> None:
        self.export_repository = export_repository
        self.agent_repository = agent_repository
        self.team_repository = team_repository

    def create_agent_export(self, *, slug: str, payload: ExportCreate, current_user: User):
        """Create export job for published agent."""
        agent = self.agent_repository.get_by_slug(slug)
        if agent is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")
        if agent.status != AgentStatus.PUBLISHED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only published agents can be exported.",
            )

        return self.export_repository.create(
            entity_type=ExportEntityType.AGENT.value,
            entity_id=agent.id,
            runtime_target=payload.runtime_target.value,
            status=ExportStatus.COMPLETED.value,
            result_url=self._build_result_url(
                entity_type=ExportEntityType.AGENT.value,
                slug=slug,
                runtime_target=payload.runtime_target.value,
            ),
            error_message=None,
            created_by=current_user.id,
        )

    def create_team_export(self, *, slug: str, payload: ExportCreate, current_user: User):
        """Create export job for published non-empty team."""
        team = self.team_repository.get_by_slug(slug)
        if team is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found.")
        if team.status != TeamStatus.PUBLISHED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only published teams can be exported.",
            )

        items = self.team_repository.list_items(team.id)
        if not items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot export empty team.",
            )

        return self.export_repository.create(
            entity_type=ExportEntityType.TEAM.value,
            entity_id=team.id,
            runtime_target=payload.runtime_target.value,
            status=ExportStatus.COMPLETED.value,
            result_url=self._build_result_url(
                entity_type=ExportEntityType.TEAM.value,
                slug=slug,
                runtime_target=payload.runtime_target.value,
            ),
            error_message=None,
            created_by=current_user.id,
        )

    def get_export(self, *, export_id: UUID, current_user: User):
        """Return export job if current user is creator."""
        job = self.export_repository.get_by_id(export_id)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Export job not found.",
            )
        if job.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the export creator can access this job.",
            )
        return job

    @staticmethod
    def _build_result_url(*, entity_type: str, slug: str, runtime_target: str) -> str:
        """Build deterministic artifact URL placeholder for MVP exports."""
        return f"/downloads/{entity_type}/{slug}/{runtime_target}.zip"
