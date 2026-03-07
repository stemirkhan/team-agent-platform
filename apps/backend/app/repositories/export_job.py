"""Repository layer for export jobs."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.export_job import ExportJob


class ExportJobRepository:
    """Data access methods for export jobs."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
        runtime_target: str,
        status: str,
        result_url: str | None,
        error_message: str | None,
        created_by: UUID,
    ) -> ExportJob:
        """Insert a new export job and return persisted entity."""
        entity = ExportJob(
            entity_type=entity_type,
            entity_id=entity_id,
            runtime_target=runtime_target,
            status=status,
            result_url=result_url,
            error_message=error_message,
            created_by=created_by,
        )
        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def get_by_id(self, export_id: UUID) -> ExportJob | None:
        """Find export job by id."""
        return self.session.scalar(select(ExportJob).where(ExportJob.id == export_id))
