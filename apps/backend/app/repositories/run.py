"""Repository layer for run and run-event persistence."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.run import Run, RunEvent


class RunRepository:
    """Data access methods for runs and run events."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        team_id: UUID | None,
        created_by: UUID,
        team_slug: str,
        team_title: str,
        runtime_target: str,
        repo_owner: str,
        repo_name: str,
        repo_full_name: str,
        base_branch: str,
        issue_number: int | None,
        issue_title: str | None,
        issue_url: str | None,
        title: str,
        summary: str | None,
        task_text: str | None,
        runtime_config_json: dict | None,
    ) -> Run:
        """Insert and return a new run."""
        entity = Run(
            team_id=team_id,
            created_by=created_by,
            team_slug=team_slug,
            team_title=team_title,
            runtime_target=runtime_target,
            repo_owner=repo_owner,
            repo_name=repo_name,
            repo_full_name=repo_full_name,
            base_branch=base_branch,
            issue_number=issue_number,
            issue_title=issue_title,
            issue_url=issue_url,
            title=title,
            summary=summary,
            task_text=task_text,
            runtime_config_json=runtime_config_json,
        )
        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def get_by_id(self, run_id: UUID) -> Run | None:
        """Find a run by primary key."""
        return self.session.scalar(select(Run).where(Run.id == run_id))

    def list_for_creator(
        self,
        *,
        created_by: UUID,
        limit: int,
        offset: int,
        status: str | None,
        repo_full_name: str | None,
    ) -> tuple[list[Run], int]:
        """Return paginated runs owned by one user."""
        query = select(Run).where(Run.created_by == created_by)
        count_query = select(func.count(Run.id)).where(Run.created_by == created_by)

        if status:
            query = query.where(Run.status == status)
            count_query = count_query.where(Run.status == status)

        if repo_full_name:
            query = query.where(Run.repo_full_name == repo_full_name)
            count_query = count_query.where(Run.repo_full_name == repo_full_name)

        query = query.order_by(Run.created_at.desc()).offset(offset).limit(limit)
        items = list(self.session.scalars(query).all())
        total = int(self.session.scalar(count_query) or 0)
        return items, total

    def update(self, run: Run, *, fields: dict[str, object]) -> Run:
        """Persist run field changes."""
        if "updated_at" not in fields:
            fields["updated_at"] = datetime.now(UTC)

        for field, value in fields.items():
            setattr(run, field, value)

        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def create_event(
        self,
        *,
        run_id: UUID,
        event_type: str,
        payload_json: dict | None,
    ) -> RunEvent:
        """Insert and return a new run event."""
        entity = RunEvent(
            run_id=run_id,
            event_type=event_type,
            payload_json=payload_json,
        )
        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def list_events(self, *, run_id: UUID) -> list[RunEvent]:
        """Return run events in creation order."""
        query = (
            select(RunEvent)
            .where(RunEvent.run_id == run_id)
            .order_by(RunEvent.created_at.asc(), RunEvent.id.asc())
        )
        return list(self.session.scalars(query).all())
