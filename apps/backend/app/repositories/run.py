"""Repository layer for run and run-event persistence."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
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
        return self.update_with_events(run, fields=fields, events=None)

    def update_with_events(
        self,
        run: Run,
        *,
        fields: dict[str, object],
        events: list[tuple[str, dict[str, object] | None]] | None,
    ) -> Run:
        """Persist run field changes and optional events in one commit."""
        if "updated_at" not in fields:
            fields["updated_at"] = datetime.now(UTC)

        for field, value in fields.items():
            setattr(run, field, value)

        self.session.add(run)
        self._add_events(run.id, events)
        self.session.commit()
        self.session.refresh(run)
        return run

    def update_if_status_in(
        self,
        run_id: UUID,
        *,
        statuses: list[str] | tuple[str, ...],
        fields: dict[str, object],
    ) -> Run | None:
        """Persist run changes only when the current status still matches an expected value."""
        return self.update_if_status_in_with_events(
            run_id,
            statuses=statuses,
            fields=fields,
            events=None,
        )

    def update_if_status_in_with_events(
        self,
        run_id: UUID,
        *,
        statuses: list[str] | tuple[str, ...],
        fields: dict[str, object],
        events: list[tuple[str, dict[str, object] | None]] | None,
    ) -> Run | None:
        """Persist run changes and optional events when the current state still matches."""
        if not statuses:
            return None

        if "updated_at" not in fields:
            fields["updated_at"] = datetime.now(UTC)

        result = self.session.execute(
            update(Run)
            .where(Run.id == run_id)
            .where(Run.status.in_(tuple(statuses)))
            .values(**fields)
        )
        if (result.rowcount or 0) == 0:
            self.session.rollback()
            return None
        self._add_events(run_id, events)
        self.session.commit()
        return self.get_by_id(run_id)

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

    def list_by_statuses(
        self,
        *,
        statuses: list[str] | tuple[str, ...],
        limit: int,
    ) -> list[Run]:
        """Return recent runs that still require lifecycle reconciliation."""
        if not statuses or limit <= 0:
            return []
        query = (
            select(Run)
            .where(Run.status.in_(tuple(statuses)))
            .order_by(Run.updated_at.asc(), Run.created_at.asc())
            .limit(limit)
        )
        return list(self.session.scalars(query).all())

    def _add_events(
        self,
        run_id: UUID,
        events: list[tuple[str, dict[str, object] | None]] | None,
    ) -> None:
        """Stage run events on the current transaction when provided."""
        if not events:
            return
        for event_type, payload_json in events:
            self.session.add(
                RunEvent(
                    run_id=run_id,
                    event_type=event_type,
                    payload_json=payload_json,
                )
            )
