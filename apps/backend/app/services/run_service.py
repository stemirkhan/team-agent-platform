"""Use-case orchestration for run preparation and materialization."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status

from app.models.export_job import RuntimeTarget
from app.models.run import RunEventType, RunStatus
from app.models.team import TeamStatus
from app.models.user import User
from app.repositories.run import RunRepository
from app.repositories.team import TeamRepository
from app.schemas.export import CodexExportOptions
from app.schemas.run import (
    RunCreate,
    RunEventListResponse,
    RunListResponse,
    RunReportCommandRead,
    RunReportPhaseRead,
    RunReportPhaseStatus,
    RunReportRead,
)
from app.schemas.terminal import TerminalSessionEventsResponse, TerminalSessionRead
from app.schemas.workspace import (
    WorkspaceCommit,
    WorkspaceFileWrite,
    WorkspaceMaterialize,
    WorkspacePrepare,
    WorkspacePullRequestCreate,
    WorkspaceRead,
)
from app.services.claude_proxy_service import ClaudeProxyService
from app.services.codex_proxy_service import CodexProxyService
from app.services.export_service import ExportService
from app.services.github_proxy_service import GitHubProxyService, GitHubProxyServiceError
from app.services.host_execution_service import HostExecutionReadinessService
from app.services.runtime_adapters import (
    BackendRuntimeAdapter,
    ClaudeRuntimeAdapter,
    CodexRuntimeAdapter,
    RuntimeAdapterError,
    RuntimeAdapterRegistry,
    RuntimeSessionRead,
)
from app.services.workspace_proxy_service import WorkspaceProxyService, WorkspaceProxyServiceError


class RunService:
    """Create and inspect local-first runtime runs."""

    _READY_MESSAGE = (
        "Workspace is prepared and the runtime bundle plus `TASK.md` are materialized. "
        "Terminal execution is the next layer."
    )
    _NO_CHANGES_TO_COMMIT_DETAIL = "Workspace has no changes to commit."

    def __init__(
        self,
        run_repository: RunRepository,
        team_repository: TeamRepository,
        export_service: ExportService,
        workspace_proxy_service: WorkspaceProxyService,
        codex_proxy_service: CodexProxyService,
        claude_proxy_service: ClaudeProxyService,
        github_proxy_service: GitHubProxyService,
        readiness_service: HostExecutionReadinessService,
        runtime_adapters: RuntimeAdapterRegistry | None = None,
    ) -> None:
        self.run_repository = run_repository
        self.team_repository = team_repository
        self.export_service = export_service
        self.workspace_proxy_service = workspace_proxy_service
        self.github_proxy_service = github_proxy_service
        self.readiness_service = readiness_service
        self.runtime_adapters = runtime_adapters or RuntimeAdapterRegistry(
            adapters=[
                CodexRuntimeAdapter(codex_proxy_service),
                ClaudeRuntimeAdapter(claude_proxy_service),
            ]
        )

    def create_run(self, payload: RunCreate, current_user: User):
        """Create a run, prepare its workspace, and materialize runtime inputs."""
        runtime_target = payload.runtime_target.value
        adapter = self._get_runtime_adapter(runtime_target)
        readiness = self.readiness_service.build_readiness()
        runtime_ready_map = getattr(readiness, "runtime_ready", None)
        effective_ready = (
            runtime_ready_map.get(runtime_target, readiness.effective_ready)
            if isinstance(runtime_ready_map, dict)
            else readiness.effective_ready
        )
        if not effective_ready:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Local execution is not ready. Open diagnostics, fix `git`/`gh`/runtime "
                    "tooling, and retry the run."
                ),
            )
        runtime_label = adapter.label

        team = self.team_repository.get_by_slug(payload.team_slug)
        if team is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found.")
        if team.status != TeamStatus.PUBLISHED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only published teams can be run right now.",
            )

        try:
            repo = self.github_proxy_service.get_repo(payload.repo_owner, payload.repo_name)
            issue = None
            if payload.issue_number is not None:
                issue = self.github_proxy_service.get_issue(
                    payload.repo_owner,
                    payload.repo_name,
                    payload.issue_number,
                )
        except GitHubProxyServiceError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

        base_branch = payload.base_branch or repo.default_branch or "main"
        run = self.run_repository.create(
            team_id=team.id,
            created_by=current_user.id,
            team_slug=team.slug,
            team_title=team.title,
            runtime_target=runtime_target,
            repo_owner=repo.owner,
            repo_name=repo.name,
            repo_full_name=repo.full_name,
            base_branch=base_branch,
            issue_number=issue.number if issue is not None else None,
            issue_title=issue.title if issue is not None else None,
            issue_url=issue.url if issue is not None else None,
            title=self._derive_title(
                payload=payload,
                team_title=team.title,
                repo_full_name=repo.full_name,
                issue_title=issue.title if issue else None,
            ),
            summary=self._derive_summary(
                payload=payload,
                issue_title=issue.title if issue else None,
            ),
            task_text=payload.task_text,
            runtime_config_json=self._build_runtime_config(
                runtime_target=runtime_target,
                codex=payload.codex,
            ),
        )
        self._append_event(
            run_id=run.id,
            event_type=RunEventType.STATUS,
            payload={
                "status": RunStatus.QUEUED.value,
                "message": "Run created.",
            },
        )

        try:
            run = self._transition_run(
                run,
                status_value=RunStatus.PREPARING,
                message="Validating inputs and preparing workspace.",
            )
            run = self._transition_run(
                run,
                status_value=RunStatus.CLONING_REPO,
                message=f"Cloning {repo.full_name} and creating a working branch.",
            )
            workspace = self.workspace_proxy_service.prepare_workspace(
                WorkspacePrepare(
                    owner=repo.owner,
                    repo=repo.name,
                    base_branch=base_branch,
                )
            )
            run = self.run_repository.update(
                run,
                fields={
                    "base_branch": workspace.base_branch,
                    "working_branch": workspace.working_branch,
                    "workspace_id": workspace.id,
                    "workspace_path": workspace.workspace_path,
                    "repo_path": workspace.repo_path,
                },
            )

            run = self._transition_run(
                run,
                status_value=RunStatus.MATERIALIZING_TEAM,
                message=(
                    f"Writing {adapter.bundle_label} "
                    "and `TASK.md` into the workspace."
                ),
            )
            workspace_files = self._build_workspace_files(
                runtime_target=runtime_target,
                team_slug=team.slug,
                team_startup_prompt=team.startup_prompt,
                payload=payload,
                repo_full_name=repo.full_name,
                base_branch=workspace.base_branch,
                working_branch=workspace.working_branch,
                issue_title=issue.title if issue else None,
                issue_number=issue.number if issue else None,
                issue_url=issue.url if issue else None,
                issue_body=issue.body if issue else None,
            )
            workspace = self.workspace_proxy_service.materialize_workspace(
                workspace.id,
                WorkspaceMaterialize(
                    files=workspace_files
                ),
            )
            run = self.run_repository.update(
                run,
                fields={
                    "workspace_path": workspace.workspace_path,
                    "repo_path": workspace.repo_path,
                },
            )
            self._append_materialization_audit_event(
                run_id=run.id,
                adapter=adapter,
                files=workspace_files,
            )
            task_markdown = self._find_workspace_file_content(workspace_files, "TASK.md")
            run = self._transition_run(
                run,
                status_value=RunStatus.STARTING_RUNTIME,
                message=f"Starting host-side {adapter.label} session.",
            )
            session = adapter.start_session(
                run_id=str(run.id),
                workspace_id=workspace.id,
                task_markdown=task_markdown,
                codex_options=payload.codex,
            )
            run = self.run_repository.update(
                run,
                fields=self._build_run_session_fields(session),
            )
            run = self._transition_run(
                run,
                status_value=RunStatus.RUNNING,
                message=f"{adapter.label} session is running in the prepared workspace.",
            )
            return run
        except (
            WorkspaceProxyServiceError,
            GitHubProxyServiceError,
            RuntimeAdapterError,
        ) as exc:
            return self._fail_run(run, detail=getattr(exc, "detail", str(exc)))
        except HTTPException as exc:
            return self._fail_run(run, detail=str(exc.detail))
        except Exception as exc:  # noqa: BLE001
            return self._fail_run(run, detail=f"Run preparation failed: {exc}")

    def list_runs(
        self,
        *,
        current_user: User,
        limit: int,
        offset: int,
        status_filter: RunStatus | None,
        repo_full_name: str | None,
    ) -> RunListResponse:
        """Return paginated runs owned by the current user."""
        status_value = status_filter.value if status_filter else None
        normalized_repo_full_name = repo_full_name.strip() or None if repo_full_name else None
        items, total = self.run_repository.list_for_creator(
            created_by=current_user.id,
            limit=limit,
            offset=offset,
            status=status_value,
            repo_full_name=normalized_repo_full_name,
        )
        items = [self._sync_run_with_runtime_session(item) for item in items]
        return RunListResponse(items=items, total=total, limit=limit, offset=offset)

    def get_run(self, run_id, current_user: User):
        """Return one run owned by the current user."""
        run = self.run_repository.get_by_id(run_id)
        if run is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
        self._ensure_owner(run.created_by, current_user.id)
        run = self._sync_run_with_runtime_session(run)
        run.run_report = self._build_run_report(run)
        return run

    def list_run_events(self, run_id, current_user: User) -> RunEventListResponse:
        """Return ordered run events for one run owned by the current user."""
        run = self.get_run(run_id, current_user)
        items = self.run_repository.list_events(run_id=run.id)
        return RunEventListResponse(items=items, total=len(items))

    def cancel_run(self, run_id, current_user: User):
        """Cancel one running host-side runtime session."""
        run = self.get_run(run_id, current_user)
        adapter = self._get_runtime_adapter(run.runtime_target)
        if run.status in {
            RunStatus.COMPLETED.value,
            RunStatus.FAILED.value,
            RunStatus.CANCELLED.value,
        }:
            return run
        if run.status == RunStatus.INTERRUPTED.value:
            run = self.run_repository.update(
                run,
                fields={
                    "status": RunStatus.CANCELLED.value,
                    "error_message": None,
                    "finished_at": datetime.now(UTC),
                },
            )
            self._append_event(
                run_id=run.id,
                event_type=RunEventType.STATUS,
                payload={
                    "status": RunStatus.CANCELLED.value,
                    "message": "Interrupted run was cancelled without resume.",
                },
            )
            return run
        try:
            session = adapter.cancel_session(str(run.id))
        except RuntimeAdapterError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

        if session.status in {"running", "resuming", "cancelled"}:
            run = self.run_repository.update(
                run,
                fields={
                    "status": RunStatus.CANCELLED.value,
                    "error_message": None,
                    "finished_at": datetime.now(UTC),
                },
            )
            self._append_event(
                run_id=run.id,
                event_type=RunEventType.STATUS,
                payload={
                    "status": RunStatus.CANCELLED.value,
                    "message": "Run cancellation was requested.",
                },
            )
        return run

    def resume_run(self, run_id, current_user: User):
        """Resume one interrupted run by restarting the persisted runtime session."""
        run = self.get_run(run_id, current_user)
        if run.status != RunStatus.INTERRUPTED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only interrupted runs can be resumed.",
            )
        if not run.workspace_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Run is missing workspace metadata required for resume.",
            )
        adapter = self._get_runtime_adapter(run.runtime_target)
        persisted_runtime_session_id = (
            run.runtime_session_id or run.codex_session_id or run.claude_session_id
        )
        if not persisted_runtime_session_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Run is missing {adapter.label} session metadata required for resume."
                ),
            )

        runtime_label = adapter.label
        runtime_event_prefix = adapter.event_prefix

        run = self._transition_run(
            run,
            status_value=RunStatus.RESUMING,
            message=f"Resuming the persisted {runtime_label} session after host interruption.",
        )
        self._append_event(
            run_id=run.id,
            event_type=RunEventType.NOTE,
            payload={
                "kind": f"{runtime_event_prefix}_resume_requested",
                "message": "Resume was requested from the interrupted run state.",
                "runtime_session_id": persisted_runtime_session_id,
                "codex_session_id": run.codex_session_id,
                "claude_session_id": run.claude_session_id,
            },
        )

        try:
            session = adapter.resume_session(str(run.id))
        except RuntimeAdapterError as exc:
            run = self.run_repository.update(
                run,
                fields={
                    "status": RunStatus.INTERRUPTED.value,
                    "error_message": exc.detail,
                    "finished_at": run.finished_at,
                },
            )
            self._append_event(
                run_id=run.id,
                event_type=RunEventType.NOTE,
                payload={
                    "kind": f"{runtime_event_prefix}_resume_failed",
                    "message": exc.detail,
                    "runtime_session_id": persisted_runtime_session_id,
                },
            )
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

        run = self.run_repository.update(
            run,
            fields={
                **self._build_run_session_fields(session),
                "status": RunStatus.RESUMING.value,
                "error_message": None,
                "finished_at": None,
            },
        )
        self._append_event(
            run_id=run.id,
            event_type=RunEventType.NOTE,
            payload={
                "kind": f"{runtime_event_prefix}_resume_started",
                "message": (
                    "Host executor started runtime resume for this run."
                    if run.runtime_target == RuntimeTarget.CLAUDE_CODE.value
                    else "Host executor started `codex exec resume` for this run."
                ),
                "resume_attempt_count": session.resume_attempt_count,
                **adapter.build_session_identity_payload(session),
            },
        )
        return run

    def get_terminal_session(self, run_id, current_user: User) -> TerminalSessionRead:
        """Return current host-side terminal session for one run."""
        run = self.get_run(run_id, current_user)
        try:
            session = self._get_runtime_adapter(run.runtime_target).get_session(str(run.id))
        except RuntimeAdapterError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
        return self._get_runtime_adapter(run.runtime_target).normalize_terminal_session(session)

    def get_terminal_events(
        self,
        run_id,
        *,
        offset: int,
        current_user: User,
    ) -> TerminalSessionEventsResponse:
        """Return incremental terminal output for one run."""
        run = self.get_run(run_id, current_user)
        try:
            events = self._get_runtime_adapter(run.runtime_target).get_events(
                str(run.id),
                offset=offset,
            )
        except RuntimeAdapterError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
        return self._get_runtime_adapter(run.runtime_target).normalize_terminal_events(events)

    def _fail_run(self, run, *, detail: str):
        """Persist failed run state and expose the updated run object."""
        failed_run = self.run_repository.update(
            run,
            fields={
                "status": RunStatus.FAILED.value,
                "error_message": detail,
                "finished_at": datetime.now(UTC),
            },
        )
        self._append_event(
            run_id=failed_run.id,
            event_type=RunEventType.STATUS,
            payload={
                "status": RunStatus.FAILED.value,
                "message": detail,
            },
        )
        self._append_event(
            run_id=failed_run.id,
            event_type=RunEventType.ERROR,
            payload={"detail": detail},
        )
        return failed_run

    def _transition_run(self, run, *, status_value: RunStatus, message: str):
        """Persist one run status transition and emit a matching event."""
        fields: dict[str, object] = {
            "status": status_value.value,
            "error_message": None,
        }
        if status_value != RunStatus.QUEUED and run.started_at is None:
            fields["started_at"] = run.created_at
        updated_run = self.run_repository.update(run, fields=fields)
        self._append_event(
            run_id=updated_run.id,
            event_type=RunEventType.STATUS,
            payload={"status": status_value.value, "message": message},
        )
        return updated_run

    def _build_workspace_files(
        self,
        *,
        runtime_target: str,
        team_slug: str,
        team_startup_prompt: str | None,
        payload: RunCreate,
        repo_full_name: str,
        base_branch: str,
        working_branch: str,
        issue_title: str | None,
        issue_number: int | None,
        issue_url: str | None,
        issue_body: str | None,
    ) -> list[WorkspaceFileWrite]:
        """Return text files that should be written into the prepared workspace."""
        adapter = self._get_runtime_adapter(runtime_target)
        task_markdown = self._build_task_markdown(
            payload=payload,
            team_startup_prompt=team_startup_prompt,
            repo_full_name=repo_full_name,
            base_branch=base_branch,
            working_branch=working_branch,
            issue_title=issue_title,
            issue_number=issue_number,
            issue_url=issue_url,
            issue_body=issue_body,
        )
        try:
            return adapter.build_workspace_files(
                export_service=self.export_service,
                team_slug=team_slug,
                task_markdown=task_markdown,
                codex_options=payload.codex,
            )
        except RuntimeAdapterError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    @classmethod
    def _build_task_markdown(
        cls,
        *,
        payload: RunCreate,
        team_startup_prompt: str | None,
        repo_full_name: str,
        base_branch: str,
        working_branch: str,
        issue_title: str | None,
        issue_number: int | None,
        issue_url: str | None,
        issue_body: str | None,
    ) -> str:
        """Render the task handoff file materialized into the repo workspace."""
        lines = [
            f"# {payload.title or issue_title or 'Execution Task'}",
        ]
        if team_startup_prompt and team_startup_prompt.strip():
            lines.extend(
                [
                    "",
                    "## Team Startup Prompt",
                    team_startup_prompt.strip(),
                ]
            )
        lines.extend(
            [
                "",
                "## Context",
                f"- Repository: `{repo_full_name}`",
                f"- Base branch: `{base_branch}`",
                f"- Working branch: `{working_branch}`",
                f"- Team: `{payload.team_slug}`",
            ]
        )
        if payload.summary:
            lines.extend(["", "## Goal Summary", payload.summary.strip()])
        if issue_number is not None:
            lines.extend(
                [
                    "",
                    "## GitHub Issue",
                    f"- Number: `#{issue_number}`",
                ]
            )
            if issue_title:
                lines.append(f"- Title: {issue_title}")
            if issue_url:
                lines.append(f"- URL: {issue_url}")
            if issue_body:
                lines.extend(["", "### Issue Body", issue_body.strip()])
        if payload.task_text:
            lines.extend(["", "## Task Instructions", payload.task_text.strip()])
        lines.extend(
            [
                "",
                "## Constraints",
                "- Keep changes scoped to the requested task.",
                "- Prefer minimal, reviewable edits over broad rewrites.",
                "- Avoid modifying unrelated files.",
            ]
        )
        return "\n".join(lines).strip() + "\n"

    @staticmethod
    def _build_runtime_config(
        *,
        runtime_target: str,
        codex: CodexExportOptions | None,
    ) -> dict[str, object]:
        """Persist selected runtime parameters for future execution steps."""
        config: dict[str, object] = {"runtime_target": runtime_target}
        if runtime_target == RuntimeTarget.CODEX.value and codex is not None:
            config["codex"] = codex.model_dump(exclude_none=True)
        return config

    def _get_runtime_adapter(self, runtime_target: str) -> BackendRuntimeAdapter:
        """Return one registered runtime adapter or raise a normalized HTTP error."""
        adapter = self.runtime_adapters.get(runtime_target)
        if adapter is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Runtime '{runtime_target}' runs are not implemented yet.",
            )
        return adapter

    @staticmethod
    def _derive_title(
        *,
        payload: RunCreate,
        team_title: str,
        repo_full_name: str,
        issue_title: str | None,
    ) -> str:
        """Return stable run title."""
        if payload.title:
            return payload.title
        if issue_title:
            return issue_title
        if payload.task_text:
            return payload.task_text.strip().splitlines()[0][:255]
        return f"{team_title} on {repo_full_name}"

    @staticmethod
    def _derive_summary(*, payload: RunCreate, issue_title: str | None) -> str | None:
        """Return short summary when available."""
        if payload.summary:
            return payload.summary
        if issue_title:
            return issue_title
        if payload.task_text:
            first_line = payload.task_text.strip().splitlines()[0]
            return first_line[:4000]
        return None

    def _append_event(
        self,
        *,
        run_id,
        event_type: RunEventType,
        payload: dict[str, object] | None,
    ) -> None:
        """Persist one run event."""
        self.run_repository.create_event(
            run_id=run_id,
            event_type=event_type.value,
            payload_json=payload,
        )

    def _append_materialization_audit_event(
        self,
        *,
        run_id,
        adapter: BackendRuntimeAdapter,
        files: list[WorkspaceFileWrite],
    ) -> None:
        """Persist one snapshot of the materialized runtime bundle before cleanup."""
        payload = adapter.build_materialization_audit_payload(files=files)
        if payload is None:
            return
        self._append_event(
            run_id=run_id,
            event_type=RunEventType.NOTE,
            payload=payload,
        )

    @staticmethod
    def _find_workspace_file_content(
        files: list[WorkspaceFileWrite],
        path: str,
    ) -> str:
        """Return one materialized file body by path."""
        for item in files:
            if item.path == path:
                return item.content
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Materialized workspace is missing `{path}`.",
        )

    def _sync_run_with_runtime_session(self, run):
        """Reconcile DB run state with host-side runtime session state when needed."""
        if run.status not in {
            RunStatus.STARTING_RUNTIME.value,
            RunStatus.STARTING_CODEX.value,
            RunStatus.RUNNING.value,
            RunStatus.RESUMING.value,
        }:
            return run

        try:
            adapter = self._get_runtime_adapter(run.runtime_target)
            session = adapter.get_session(str(run.id))
        except RuntimeAdapterError as exc:
            if exc.status_code == 404:
                return self._fail_run(
                    run,
                    detail=(
                        f"Host-side {adapter.label} session state was lost. "
                        "This usually means the host executor restarted during the run. "
                        "Relaunch the run."
                    ),
                )
            return self._fail_run(run, detail=exc.detail)

        if session.status == "running":
            fields = self._build_run_session_fields(session)
            auto_resume_advanced = (
                session.recovered_from_restart
                and session.resume_attempt_count > run.resume_attempt_count
            )
            if run.status == RunStatus.RESUMING.value:
                updated = self.run_repository.update(
                    run,
                    fields={
                        **fields,
                        "status": RunStatus.RUNNING.value,
                        "error_message": None,
                        "finished_at": None,
                    },
                )
                self._append_event(
                    run_id=updated.id,
                    event_type=RunEventType.STATUS,
                    payload={
                        "status": RunStatus.RUNNING.value,
                        "message": f"{adapter.label} session resumed and is running again.",
                    },
                )
                self._append_event(
                    run_id=updated.id,
                    event_type=RunEventType.NOTE,
                    payload=self._build_runtime_resume_completed_note_payload(
                        adapter=adapter,
                        session=session,
                        recovered_before_poll=False,
                    ),
                )
                return updated
            if auto_resume_advanced:
                updated = self.run_repository.update(
                    run,
                    fields={
                        **fields,
                        "status": RunStatus.RUNNING.value,
                        "error_message": None,
                        "finished_at": None,
                    },
                )
                self._append_event(
                    run_id=updated.id,
                    event_type=RunEventType.NOTE,
                    payload=self._build_runtime_resume_completed_note_payload(
                        adapter=adapter,
                        session=session,
                        recovered_before_poll=True,
                    ),
                )
                return updated
            if fields:
                return self.run_repository.update(run, fields=fields)
            return run

        if session.status == "resuming":
            previous_status = run.status
            updated = self.run_repository.update(
                run,
                fields={
                    **self._build_run_session_fields(session),
                    "status": RunStatus.RESUMING.value,
                    "error_message": None,
                    "finished_at": None,
                },
            )
            if previous_status != RunStatus.RESUMING.value and session.recovered_from_restart:
                self._append_event(
                    run_id=updated.id,
                    event_type=RunEventType.STATUS,
                    payload={
                        "status": RunStatus.RESUMING.value,
                        "message": f"Host executor restarted and automatic {adapter.label} recovery is in progress.",
                    },
                )
                self._append_event(
                    run_id=updated.id,
                    event_type=RunEventType.NOTE,
                    payload=self._build_runtime_resume_started_note_payload(
                        adapter=adapter,
                        session=session,
                    ),
                )
            return updated

        self._append_runtime_terminal_audit_event(
            run_id=run.id,
            adapter=adapter,
        )

        if session.status == "interrupted":
            interrupted_at = self._parse_terminal_timestamp(session.interrupted_at)
            updated = self.run_repository.update(
                run,
                fields={
                    **self._build_run_session_fields(session),
                    "status": RunStatus.INTERRUPTED.value,
                    "error_message": session.error_message,
                    "finished_at": interrupted_at or datetime.now(UTC),
                    "interrupted_at": interrupted_at or datetime.now(UTC),
                },
            )
            self._append_event(
                run_id=updated.id,
                event_type=RunEventType.STATUS,
                payload={
                    "status": RunStatus.INTERRUPTED.value,
                    "message": session.error_message or f"{adapter.label} session was interrupted.",
                },
            )
            self._append_event(
                run_id=updated.id,
                event_type=RunEventType.NOTE,
                payload=self._build_runtime_interrupted_note_payload(
                    adapter=adapter,
                    session=session,
                ),
            )
            if session.resumable:
                self._append_event(
                    run_id=updated.id,
                    event_type=RunEventType.NOTE,
                    payload=self._build_runtime_resume_available_note_payload(
                        adapter=adapter,
                        session=session,
                    ),
                )
            return updated

        if session.status == "completed":
            run = self.run_repository.update(run, fields=self._build_run_session_fields(session))
            return self._finalize_completed_run(run, session)

        if session.status == "cancelled":
            updated = self.run_repository.update(
                run,
                fields={
                    **self._build_run_session_fields(session),
                    "status": RunStatus.CANCELLED.value,
                    "error_message": None,
                    "finished_at": self._parse_terminal_timestamp(session.finished_at)
                    or datetime.now(UTC),
                },
            )
            self._append_event(
                run_id=updated.id,
                event_type=RunEventType.STATUS,
                payload={
                    "status": RunStatus.CANCELLED.value,
                    "message": f"{adapter.label} session was cancelled.",
                },
            )
            return updated

        updated = self.run_repository.update(
            run,
            fields={
                **self._build_run_session_fields(session),
                "status": RunStatus.FAILED.value,
                "error_message": session.error_message or f"{adapter.label} session failed.",
                "finished_at": self._parse_terminal_timestamp(session.finished_at)
                or datetime.now(UTC),
            },
        )
        self._append_event(
            run_id=updated.id,
            event_type=RunEventType.STATUS,
            payload={
                "status": RunStatus.FAILED.value,
                "message": updated.error_message,
            },
        )
        self._append_event(
            run_id=updated.id,
            event_type=RunEventType.ERROR,
            payload={"detail": updated.error_message},
        )
        return updated

    def _build_runtime_resume_completed_note_payload(
        self,
        *,
        adapter: BackendRuntimeAdapter,
        session: RuntimeSessionRead,
        recovered_before_poll: bool,
    ) -> dict[str, object]:
        """Return the standardized runtime note payload for completed resume recovery."""
        if recovered_before_poll:
            payload = {
                "kind": f"{adapter.event_prefix}_auto_resume_completed",
                "message": (
                    f"Host executor recovered the {adapter.label} session automatically "
                    "before the next poll and terminal output is live again."
                ),
                "resume_attempt_count": session.resume_attempt_count,
            }
        else:
            payload = {
                "kind": (
                    f"{adapter.event_prefix}_auto_resume_completed"
                    if session.recovered_from_restart
                    else f"{adapter.event_prefix}_resume_completed"
                ),
                "message": (
                    "Automatic recovery completed and terminal output is live again."
                    if session.recovered_from_restart
                    else "Resume completed and terminal output is live again."
                ),
                "resume_attempt_count": session.resume_attempt_count,
            }
        return {
            **payload,
            **adapter.build_note_session_payload(session),
        }

    def _build_runtime_resume_started_note_payload(
        self,
        *,
        adapter: BackendRuntimeAdapter,
        session: RuntimeSessionRead,
    ) -> dict[str, object]:
        """Return the standardized runtime note payload for automatic resume start."""
        return {
            "kind": f"{adapter.event_prefix}_auto_resume_started",
            "message": (
                "Host executor restarted and semantic resume started automatically "
                f"from the persisted {adapter.label} session."
            ),
            "resume_attempt_count": session.resume_attempt_count,
            **adapter.build_note_session_payload(session),
        }

    def _build_runtime_interrupted_note_payload(
        self,
        *,
        adapter: BackendRuntimeAdapter,
        session: RuntimeSessionRead,
    ) -> dict[str, object]:
        """Return the standardized runtime note payload for interrupted sessions."""
        return {
            "kind": f"{adapter.event_prefix}_session_interrupted",
            "message": session.error_message or f"{adapter.label} session was interrupted.",
            "resumable": session.resumable,
            "resume_attempt_count": session.resume_attempt_count,
            **adapter.build_note_session_payload(session),
        }

    def _build_runtime_resume_available_note_payload(
        self,
        *,
        adapter: BackendRuntimeAdapter,
        session: RuntimeSessionRead,
    ) -> dict[str, object]:
        """Return the standardized runtime note payload when resume is available."""
        return {
            "kind": f"{adapter.event_prefix}_resume_available",
            "message": (
                f"The interrupted {adapter.label} session can be resumed "
                "from the same run."
            ),
            **adapter.build_note_session_payload(session),
        }

    def _build_run_session_fields(
        self,
        session: RuntimeSessionRead,
    ) -> dict[str, object]:
        """Return run fields that mirror host-side runtime session metadata."""
        adapter = self._get_runtime_adapter(
            getattr(session, "runtime_target", None) or self._infer_runtime_target_from_session(session)
        )
        fields: dict[str, object] = {
            **adapter.build_session_identity_payload(session),
            "transport_kind": session.transport_kind,
            "transport_ref": session.transport_ref,
            "resume_attempt_count": session.resume_attempt_count,
        }
        interrupted_at = RunService._parse_terminal_timestamp(session.interrupted_at)
        if interrupted_at is not None:
            fields["interrupted_at"] = interrupted_at
        return fields

    @staticmethod
    def _infer_runtime_target_from_session(session: RuntimeSessionRead) -> str:
        """Infer runtime target from a runtime-specific session payload shape."""
        if getattr(session, "claude_session_id", None) is not None:
            return RuntimeTarget.CLAUDE_CODE.value
        return RuntimeTarget.CODEX.value

    @staticmethod
    def _parse_terminal_timestamp(value: str | None) -> datetime | None:
        """Parse one host-side UTC timestamp emitted in terminal/session payloads."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _append_runtime_terminal_audit_event(
        self,
        *,
        run_id,
        adapter: BackendRuntimeAdapter,
    ) -> None:
        """Persist one runtime-specific execution trace when the runtime exposes it."""
        try:
            payload = adapter.get_terminal_audit_payload(str(run_id))
        except RuntimeAdapterError as exc:
            self._append_event(
                run_id=run_id,
                event_type=RunEventType.NOTE,
                payload={
                    "kind": f"{adapter.event_prefix}_execution_trace",
                    "message": f"{adapter.label} terminal trace could not be captured.",
                    "trace_capture_error": exc.detail,
                },
            )
            return

        if payload is None:
            return
        self._append_event(
            run_id=run_id,
            event_type=RunEventType.NOTE,
            payload=payload,
        )

    def _finalize_completed_run(self, run, session: RuntimeSessionRead):
        """Convert a completed runtime session into commit, push, and draft-PR artifacts."""
        if run.workspace_id is None:
            return self._fail_run(
                run,
                detail="Run is missing workspace metadata required for post-run finalization.",
            )

        adapter = self._get_runtime_adapter(run.runtime_target)
        runtime_label = adapter.label
        runtime_slug = adapter.summary_label

        try:
            run = self._transition_run(
                run,
                status_value=RunStatus.COMMITTING,
                message=(
                    f"Cleaning temporary runtime files and preparing a git commit "
                    f"for the {runtime_slug} changes."
                ),
            )
            workspace = self.workspace_proxy_service.cleanup_workspace(run.workspace_id)

            if not workspace.has_changes:
                return self._complete_run(
                    run,
                    summary_text=session.summary_text,
                    message=(
                        f"{runtime_label} session completed with no repository changes to commit."
                    ),
                )

            recovered = self._recover_from_existing_workspace_finalization(
                run,
                summary_text=session.summary_text,
            )
            if recovered is not None:
                return recovered

            run = self._transition_run(
                run,
                status_value=RunStatus.COMMITTING,
                message=f"Creating a git commit from the {runtime_slug} changes.",
            )
            try:
                workspace = self.workspace_proxy_service.commit_workspace(
                    run.workspace_id,
                    WorkspaceCommit(message=self._build_commit_message(run)),
                )
            except WorkspaceProxyServiceError as exc:
                if exc.detail == self._NO_CHANGES_TO_COMMIT_DETAIL:
                    recovered = self._recover_from_existing_workspace_finalization(
                        run,
                        summary_text=session.summary_text,
                    )
                    if recovered is not None:
                        return recovered
                raise
            run = self.run_repository.update(
                run,
                fields={
                    "working_branch": workspace.working_branch,
                    "workspace_path": workspace.workspace_path,
                    "repo_path": workspace.repo_path,
                    "summary": session.summary_text or run.summary,
                },
            )

            run = self._transition_run(
                run,
                status_value=RunStatus.PUSHING,
                message="Pushing the working branch to origin.",
            )
            workspace = self.workspace_proxy_service.push_workspace(run.workspace_id)

            run = self._transition_run(
                run,
                status_value=RunStatus.CREATING_PR,
                message=f"Creating a draft pull request for the {runtime_slug} changes.",
            )
            workspace = self.workspace_proxy_service.create_pull_request(
                run.workspace_id,
                WorkspacePullRequestCreate(
                    title=self._build_pr_title(run),
                    body=self._build_pr_body(run),
                    draft=True,
                ),
            )
            return self._complete_run(
                run,
                summary_text=session.summary_text,
                message="Draft pull request created from the working branch.",
                pr_url=workspace.pull_request_url,
            )
        except WorkspaceProxyServiceError as exc:
            return self._fail_run(run, detail=exc.detail)
        except Exception as exc:  # noqa: BLE001
            return self._fail_run(run, detail=f"Run finalization failed: {exc}")

    def _complete_run(
        self,
        run,
        *,
        summary_text: str | None,
        message: str,
        pr_url: str | None = None,
    ):
        """Persist final completed state after runtime and optional SCM post-processing."""
        fields: dict[str, object] = {
            "status": RunStatus.COMPLETED.value,
            "error_message": None,
            "finished_at": datetime.now(UTC),
        }
        if pr_url:
            fields["pr_url"] = pr_url
        if not run.summary and summary_text:
            fields["summary"] = summary_text
        updated = self.run_repository.update(run, fields=fields)
        self._append_event(
            run_id=updated.id,
            event_type=RunEventType.STATUS,
            payload={
                "status": RunStatus.COMPLETED.value,
                "message": message,
            },
        )
        if pr_url:
            self._append_event(
                run_id=updated.id,
                event_type=RunEventType.NOTE,
                payload={
                    "message": "Draft pull request is ready.",
                    "pr_url": pr_url,
                },
            )
        return updated

    def _recover_from_existing_workspace_finalization(
        self,
        run,
        *,
        summary_text: str | None,
    ):
        """Resume or complete finalization from the current workspace state."""
        if run.workspace_id is None:
            return None

        workspace = self.workspace_proxy_service.get_workspace(run.workspace_id)
        adapter = self._get_runtime_adapter(run.runtime_target)
        runtime_label = adapter.label
        runtime_slug = adapter.summary_label
        run = self.run_repository.update(
            run,
            fields={
                "working_branch": workspace.working_branch,
                "workspace_path": workspace.workspace_path,
                "repo_path": workspace.repo_path,
                "summary": summary_text or run.summary,
            },
        )

        if workspace.status == "pull_request_created":
            return self._complete_run(
                run,
                summary_text=summary_text,
                message="Draft pull request created from the working branch.",
                pr_url=workspace.pull_request_url,
            )

        if workspace.status == "pushed":
            run = self._transition_run(
                run,
                status_value=RunStatus.CREATING_PR,
                message=f"Creating a draft pull request for the {runtime_slug} changes.",
            )
            workspace = self.workspace_proxy_service.create_pull_request(
                run.workspace_id,
                WorkspacePullRequestCreate(
                    title=self._build_pr_title(run),
                    body=self._build_pr_body(run),
                    draft=True,
                ),
            )
            return self._complete_run(
                run,
                summary_text=summary_text,
                message="Draft pull request created from the working branch.",
                pr_url=workspace.pull_request_url,
            )

        if workspace.status == "committed":
            run = self._transition_run(
                run,
                status_value=RunStatus.PUSHING,
                message="Pushing the working branch to origin.",
            )
            workspace = self.workspace_proxy_service.push_workspace(run.workspace_id)
            run = self._transition_run(
                run,
                status_value=RunStatus.CREATING_PR,
                message=f"Creating a draft pull request for the {runtime_slug} changes.",
            )
            workspace = self.workspace_proxy_service.create_pull_request(
                run.workspace_id,
                WorkspacePullRequestCreate(
                    title=self._build_pr_title(run),
                    body=self._build_pr_body(run),
                    draft=True,
                ),
            )
            return self._complete_run(
                run,
                summary_text=summary_text,
                message="Draft pull request created from the working branch.",
                pr_url=workspace.pull_request_url,
            )

        if workspace.status == "prepared" and not workspace.has_changes:
            return self._complete_run(
                run,
                summary_text=summary_text,
                message=(
                    f"{runtime_label} session completed with no repository changes to commit."
                ),
            )

        return None

    def _build_commit_message(self, run) -> str:
        """Return a deterministic git commit message for one finalized run."""
        title = run.title.strip()
        runtime_slug = self._get_runtime_adapter(run.runtime_target).summary_label
        if run.issue_number is not None:
            return f"chore(run): address #{run.issue_number} {title[:140]}".strip()
        return f"chore(run): apply {runtime_slug} changes for {title[:160]}".strip()

    @staticmethod
    def _build_pr_title(run) -> str:
        """Return a stable draft PR title for one run."""
        if run.issue_number is not None:
            return f"[tap] #{run.issue_number} {run.title}".strip()
        return f"[tap] {run.title}".strip()

    @staticmethod
    def _build_pr_body(run) -> str:
        """Return a concise PR body describing the automated run context."""
        lines = [
            "## Team Agent Platform run",
            "",
            f"- Team: `{run.team_title}`",
            f"- Repository: `{run.repo_full_name}`",
            f"- Base branch: `{run.base_branch}`",
            f"- Working branch: `{run.working_branch or '-'}`",
        ]
        if run.issue_number is not None:
            lines.append(f"- Issue: #{run.issue_number}")
        if run.issue_url:
            lines.append(f"- Issue URL: {run.issue_url}")
        if run.summary:
            lines.extend(["", "## Summary", run.summary.strip()])
        if run.task_text:
            lines.extend(["", "## Task", run.task_text.strip()])
        lines.extend(
            [
                "",
                "## Notes",
                "- This draft PR was created by the local host-execution flow.",
                "- Review the diff and run project-specific checks before merging.",
            ]
        )
        body = "\n".join(lines).strip()
        return body[:19_500]

    def _build_run_report(self, run) -> RunReportRead:
        """Build a phase-oriented run report from structured events and workspace metadata."""
        events = self.run_repository.list_events(run_id=run.id)
        workspace = self._try_get_workspace(run.workspace_id)
        runtime_label = self._get_runtime_adapter(run.runtime_target).label

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
        """Determine which phase failed/cancelled based on the latest status transition."""
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

    @staticmethod
    def _ensure_owner(owner_id, current_user_id) -> None:
        """Require current user to own the requested run."""
        if owner_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the run creator can access this run.",
            )
