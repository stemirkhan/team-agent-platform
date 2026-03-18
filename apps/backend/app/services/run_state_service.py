"""Atomic run state transitions and event persistence helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.models.run import RunEventType, RunStatus
from app.repositories.run import RunRepository


@dataclass(frozen=True, slots=True)
class RunEventSpec:
    """One run event to persist alongside a state transition."""

    event_type: RunEventType
    payload: dict[str, object] | None


class RunStateService:
    """Apply run updates together with matching persisted events."""

    def __init__(self, run_repository: RunRepository) -> None:
        self.run_repository = run_repository

    def append_event(
        self,
        *,
        run_id,
        event_type: RunEventType,
        payload: dict[str, object] | None,
    ) -> None:
        """Persist a standalone run event."""
        self.run_repository.create_event(
            run_id=run_id,
            event_type=event_type.value,
            payload_json=payload,
        )

    def update_run(
        self,
        run,
        *,
        fields: dict[str, object],
        events: list[RunEventSpec] | None = None,
    ):
        """Persist run field changes and optional events in one commit."""
        return self.run_repository.update_with_events(
            run,
            fields=fields,
            events=self._serialize_events(events),
        )

    def update_run_if_status_in(
        self,
        run_id,
        *,
        statuses: list[str] | tuple[str, ...],
        fields: dict[str, object],
        events: list[RunEventSpec] | None = None,
    ):
        """Persist run changes when the current state still matches one expected status."""
        return self.run_repository.update_if_status_in_with_events(
            run_id,
            statuses=statuses,
            fields=fields,
            events=self._serialize_events(events),
        )

    def transition_run(self, run, *, status_value: RunStatus, message: str):
        """Persist a status transition with the matching status event."""
        fields: dict[str, object] = {
            "status": status_value.value,
            "error_message": None,
        }
        if status_value != RunStatus.QUEUED and run.started_at is None:
            fields["started_at"] = run.created_at
        return self.update_run(
            run,
            fields=fields,
            events=[
                RunEventSpec(
                    event_type=RunEventType.STATUS,
                    payload={"status": status_value.value, "message": message},
                )
            ],
        )

    def fail_run(self, run, *, detail: str):
        """Persist a failed run together with status and error events."""
        return self.update_run(
            run,
            fields={
                "status": RunStatus.FAILED.value,
                "error_message": detail,
                "finished_at": datetime.now(UTC),
            },
            events=[
                RunEventSpec(
                    event_type=RunEventType.STATUS,
                    payload={"status": RunStatus.FAILED.value, "message": detail},
                ),
                RunEventSpec(
                    event_type=RunEventType.ERROR,
                    payload={"detail": detail},
                ),
            ],
        )

    def complete_run(
        self,
        run,
        *,
        summary_text: str | None,
        message: str,
        pr_url: str | None = None,
    ):
        """Persist a completed run and its final user-facing status events."""
        fields: dict[str, object] = {
            "status": RunStatus.COMPLETED.value,
            "error_message": None,
            "finished_at": datetime.now(UTC),
        }
        if pr_url:
            fields["pr_url"] = pr_url
        if not run.summary and summary_text:
            fields["summary"] = summary_text

        events = [
            RunEventSpec(
                event_type=RunEventType.STATUS,
                payload={"status": RunStatus.COMPLETED.value, "message": message},
            )
        ]
        if pr_url:
            events.append(
                RunEventSpec(
                    event_type=RunEventType.NOTE,
                    payload={
                        "message": "Draft pull request is ready.",
                        "pr_url": pr_url,
                    },
                )
            )

        return self.update_run(run, fields=fields, events=events)

    @staticmethod
    def _serialize_events(
        events: list[RunEventSpec] | None,
    ) -> list[tuple[str, dict[str, object] | None]] | None:
        """Convert event specs into the repository wire format."""
        if not events:
            return None
        return [(item.event_type.value, item.payload) for item in events]
