"""Structured reporting over persisted run events and workspace metadata."""

from __future__ import annotations

from app.models.run import RunEventType, RunStatus
from app.schemas.run import (
    RunReportCommandRead,
    RunReportPhaseRead,
    RunReportPhaseStatus,
    RunReportRead,
)
from app.schemas.workspace import WorkspaceRead
from app.services.runtime_adapters import RuntimeAdapterRegistry
from app.services.workspace_proxy_service import WorkspaceProxyService, WorkspaceProxyServiceError


class RunReportService:
    """Build phase-oriented run reports from run state and persisted events."""

    def __init__(
        self,
        *,
        run_repository,
        workspace_proxy_service: WorkspaceProxyService,
        runtime_adapters: RuntimeAdapterRegistry,
    ) -> None:
        self.run_repository = run_repository
        self.workspace_proxy_service = workspace_proxy_service
        self.runtime_adapters = runtime_adapters

    def build_run_report(self, run) -> RunReportRead:
        """Build a phase-oriented run report from structured events and workspace metadata."""
        events = self.run_repository.list_events(run_id=run.id)
        workspace = self._try_get_workspace(run.workspace_id)
        runtime_label = self._get_runtime_label(run.runtime_target)

        phases: dict[str, RunReportPhaseRead] = {
            "preparation": RunReportPhaseRead(
                key="preparation",
                order=1,
                status="not_started",
                description="Workspace and task scaffolding preparation.",
            ),
            "runtime": RunReportPhaseRead(
                key="runtime",
                order=2,
                status="not_started",
                description=f"Host-side {runtime_label} terminal execution.",
            ),
            "git_pr": RunReportPhaseRead(
                key="git_pr",
                order=3,
                status="not_started",
                description="Commit, push, and draft pull request finalization.",
            ),
        }

        failure_phase = self._resolve_failure_phase(events)

        for event in events:
            payload = event.payload_json or {}
            if event.event_type == RunEventType.STATUS.value:
                status_value = payload.get("status") if isinstance(payload, dict) else None
                if not isinstance(status_value, str):
                    continue
                phase_key = self._status_to_phase(status_value)
                if phase_key is None:
                    continue
                phase = phases[phase_key]
                phase.first_event_at = phase.first_event_at or event.created_at
                phase.last_event_at = event.created_at
                message = payload.get("message") if isinstance(payload, dict) else None
                if isinstance(message, str) and message.strip():
                    phase.description = message.strip()
            elif event.event_type == RunEventType.NOTE.value and isinstance(payload, dict):
                label = payload.get("label")
                commands = self._parse_report_commands(payload.get("items"))

                if label == "repo-setup" and commands:
                    phase = phases["preparation"]
                    phase.first_event_at = phase.first_event_at or event.created_at
                    phase.last_event_at = event.created_at
                    phase.commands.extend(commands)
                if label == "repo-checks" and commands:
                    phase = phases["git_pr"]
                    phase.first_event_at = phase.first_event_at or event.created_at
                    phase.last_event_at = event.created_at
                    phase.commands.extend(commands)

        for key, phase in phases.items():
            phase.status = self._resolve_phase_status(
                phase_key=key,
                run_status=run.status,
                has_events=phase.first_event_at is not None,
                failure_phase=failure_phase,
            )

        git_phase = phases["git_pr"]
        git_phase.meta = {
            "working_branch": run.working_branch,
            "commit_sha": workspace.last_commit_sha if workspace is not None else None,
            "pr_url": run.pr_url or (workspace.pull_request_url if workspace is not None else None),
        }

        return RunReportRead(phases=sorted(phases.values(), key=lambda item: item.order))

    def _try_get_workspace(self, workspace_id: str | None) -> WorkspaceRead | None:
        """Best-effort workspace snapshot lookup for structured run reporting."""
        if not workspace_id:
            return None
        try:
            return self.workspace_proxy_service.get_workspace(workspace_id)
        except WorkspaceProxyServiceError:
            return None

    def _get_runtime_label(self, runtime_target: str) -> str:
        """Return a runtime adapter label for user-facing report descriptions."""
        adapter = self.runtime_adapters.get(runtime_target)
        return adapter.label if adapter is not None else runtime_target

    @staticmethod
    def _status_to_phase(status_value: str) -> str | None:
        """Map run status values to run report phase keys."""
        mapping = {
            RunStatus.PREPARING.value: "preparation",
            RunStatus.CLONING_REPO.value: "preparation",
            RunStatus.MATERIALIZING_TEAM.value: "preparation",
            RunStatus.RUNNING_SETUP.value: "preparation",
            RunStatus.STARTING_RUNTIME.value: "runtime",
            RunStatus.STARTING_CODEX.value: "runtime",
            RunStatus.RUNNING.value: "runtime",
            RunStatus.INTERRUPTED.value: "runtime",
            RunStatus.RESUMING.value: "runtime",
            RunStatus.RUNNING_CHECKS.value: "git_pr",
            RunStatus.COMMITTING.value: "git_pr",
            RunStatus.PUSHING.value: "git_pr",
            RunStatus.CREATING_PR.value: "git_pr",
            RunStatus.COMPLETED.value: "git_pr",
        }
        return mapping.get(status_value)

    def _resolve_failure_phase(self, events) -> str | None:
        """Determine which phase failed or was cancelled from status events."""
        last_phase: str | None = None
        for event in events:
            if event.event_type != RunEventType.STATUS.value:
                continue
            payload = event.payload_json or {}
            status_value = payload.get("status") if isinstance(payload, dict) else None
            if not isinstance(status_value, str):
                continue
            if status_value in {
                RunStatus.INTERRUPTED.value,
                RunStatus.FAILED.value,
                RunStatus.CANCELLED.value,
            }:
                return last_phase
            phase = self._status_to_phase(status_value)
            if phase is not None:
                last_phase = phase
        return None

    @staticmethod
    def _parse_report_commands(items: object) -> list[RunReportCommandRead]:
        """Convert note payload command entries into report command records."""
        if not isinstance(items, list):
            return []
        parsed: list[RunReportCommandRead] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            command = raw.get("command")
            exit_code = raw.get("exit_code")
            succeeded = raw.get("succeeded")
            if not isinstance(command, str) or not isinstance(exit_code, int):
                continue
            if not isinstance(succeeded, bool):
                succeeded = exit_code == 0
            output = raw.get("output") if isinstance(raw.get("output"), str) else None
            started_at = raw.get("started_at") if isinstance(raw.get("started_at"), str) else None
            finished_raw = raw.get("finished_at")
            finished_at = finished_raw if isinstance(finished_raw, str) else None
            parsed.append(
                RunReportCommandRead(
                    command=command,
                    exit_code=exit_code,
                    succeeded=succeeded,
                    output=output[:4000] if output else None,
                    started_at=started_at,
                    finished_at=finished_at,
                )
            )
        return parsed

    def _resolve_phase_status(
        self,
        *,
        phase_key: str,
        run_status: str,
        has_events: bool,
        failure_phase: str | None,
    ) -> RunReportPhaseStatus:
        """Compute one report-phase status from run state and event history."""
        run_phase = self._status_to_phase(run_status)

        if run_status == RunStatus.CANCELLED.value:
            if failure_phase == phase_key:
                return "cancelled"
            if has_events:
                return "completed"
            return "not_started"

        if run_status == RunStatus.FAILED.value:
            if failure_phase == phase_key:
                return "failed"
            if has_events:
                return "completed"
            return "not_started"

        if run_status == RunStatus.INTERRUPTED.value:
            if failure_phase == phase_key:
                return "interrupted"
            if has_events:
                return "completed"
            return "not_started"

        if run_status == RunStatus.COMPLETED.value:
            if has_events:
                return "completed"
            return "not_started"

        if run_status == RunStatus.RESUMING.value and run_phase == phase_key:
            return "resuming"

        if run_phase == phase_key:
            return "running"
        if has_events:
            return "completed"
        return "not_started"
