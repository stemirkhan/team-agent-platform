"""Use-case orchestration for run preparation, lifecycle, and reporting."""

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
from app.schemas.run import RunCreate, RunEventListResponse, RunListResponse, RunReportRead
from app.schemas.terminal import TerminalSessionEventsResponse, TerminalSessionRead
from app.schemas.workspace import WorkspaceMaterialize, WorkspacePrepare
from app.services.claude_proxy_service import ClaudeProxyService
from app.services.codex_proxy_service import CodexProxyService
from app.services.export_service import ExportService
from app.services.github_proxy_service import GitHubProxyService, GitHubProxyServiceError
from app.services.host_execution_service import HostExecutionReadinessService
from app.services.run_report_service import RunReportService
from app.services.run_session_sync_service import RunSessionSyncService
from app.services.run_state_service import RunEventSpec, RunStateService
from app.services.run_workspace_materializer import RunWorkspaceMaterializer
from app.services.runtime_adapters import (
    ClaudeRuntimeAdapter,
    CodexRuntimeAdapter,
    RuntimeAdapterError,
    RuntimeAdapterRegistry,
)
from app.services.workspace_proxy_service import WorkspaceProxyService, WorkspaceProxyServiceError


class RunService:
    """Create and inspect local-first runtime runs."""

    _READY_MESSAGE = (
        "Workspace is prepared and the runtime bundle plus `TASK.md` are materialized. "
        "Terminal execution is the next layer."
    )

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
        state_service: RunStateService | None = None,
        session_sync_service: RunSessionSyncService | None = None,
        report_service: RunReportService | None = None,
        workspace_materializer: RunWorkspaceMaterializer | None = None,
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
        self.state_service = state_service or RunStateService(run_repository)
        self.session_sync_service = session_sync_service or RunSessionSyncService(
            run_repository=run_repository,
            workspace_proxy_service=workspace_proxy_service,
            runtime_adapters=self.runtime_adapters,
            state_service=self.state_service,
        )
        self.report_service = report_service or RunReportService(
            run_repository=run_repository,
            workspace_proxy_service=workspace_proxy_service,
            runtime_adapters=self.runtime_adapters,
        )
        self.workspace_materializer = workspace_materializer or RunWorkspaceMaterializer(
            export_service=export_service,
            runtime_adapters=self.runtime_adapters,
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
            payload={"status": RunStatus.QUEUED.value, "message": "Run created."},
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
                    repo_full_name=repo.full_name,
                    repo_url=repo.url,
                    default_branch=repo.default_branch,
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
                message=f"Writing {adapter.bundle_label} and `TASK.md` into the workspace.",
            )
            workspace_files = self._build_workspace_files(
                run=run,
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
                WorkspaceMaterialize(files=workspace_files),
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
            run = self.state_service.update_run(
                run,
                fields=self._build_run_session_fields(session),
            )
            run = self._transition_run(
                run,
                status_value=RunStatus.RUNNING,
                message=f"{adapter.label} session is running in the prepared workspace.",
            )
            return run
        except (WorkspaceProxyServiceError, GitHubProxyServiceError, RuntimeAdapterError) as exc:
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
        """Return paginated runs owned by the current user without mutating lifecycle state."""
        status_value = status_filter.value if status_filter else None
        normalized_repo_full_name = repo_full_name.strip() or None if repo_full_name else None
        items, total = self.run_repository.list_for_creator(
            created_by=current_user.id,
            limit=limit,
            offset=offset,
            status=status_value,
            repo_full_name=normalized_repo_full_name,
        )
        return RunListResponse(items=items, total=total, limit=limit, offset=offset)

    def get_run(
        self,
        run_id,
        current_user: User,
        *,
        sync_session: bool = False,
        include_report: bool = False,
    ):
        """Return one run owned by the current user."""
        run = self._get_owned_run(run_id, current_user)
        if sync_session:
            run = self.reconcile_run_entity(run)
        run.run_report = self._build_run_report(run) if include_report else None
        return run

    def get_run_report(
        self,
        run_id,
        current_user: User,
        *,
        sync_session: bool = False,
    ) -> RunReportRead:
        """Return the structured execution report for one owned run."""
        run = self._get_owned_run(run_id, current_user)
        if sync_session:
            run = self.reconcile_run_entity(run)
        return self._build_run_report(run)

    def list_run_events(self, run_id, current_user: User) -> RunEventListResponse:
        """Return ordered run events for one run owned by the current user."""
        run = self._get_owned_run(run_id, current_user)
        items = self.run_repository.list_events(run_id=run.id)
        return RunEventListResponse(items=items, total=len(items))

    def list_reconcilable_runs(self, *, limit: int):
        """Return the active runs that still require backend-owned lifecycle reconciliation."""
        return self.run_repository.list_by_statuses(
            statuses=self.session_sync_service.ACTIVE_RUN_STATUSES,
            limit=limit,
        )

    def reconcile_run_entity(self, run):
        """Advance one active run using host-side runtime session state."""
        return self._sync_run_with_runtime_session(run)

    def cancel_run(self, run_id, current_user: User):
        """Cancel one running host-side runtime session."""
        run = self.reconcile_run_entity(self._get_owned_run(run_id, current_user))
        adapter = self._get_runtime_adapter(run.runtime_target)
        if run.status in {
            RunStatus.COMPLETED.value,
            RunStatus.FAILED.value,
            RunStatus.CANCELLED.value,
        }:
            return run
        if run.status == RunStatus.INTERRUPTED.value:
            return self.state_service.update_run(
                run,
                fields={
                    "status": RunStatus.CANCELLED.value,
                    "error_message": None,
                    "finished_at": datetime.now(UTC),
                },
                events=[
                    RunEventSpec(
                        event_type=RunEventType.STATUS,
                        payload={
                            "status": RunStatus.CANCELLED.value,
                            "message": "Interrupted run was cancelled without resume.",
                        },
                    )
                ],
            )

        try:
            session = adapter.cancel_session(str(run.id))
        except RuntimeAdapterError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

        if session.status in {"running", "resuming", "cancelled"}:
            run = self.state_service.update_run(
                run,
                fields={
                    "status": RunStatus.CANCELLED.value,
                    "error_message": None,
                    "finished_at": datetime.now(UTC),
                },
                events=[
                    RunEventSpec(
                        event_type=RunEventType.STATUS,
                        payload={
                            "status": RunStatus.CANCELLED.value,
                            "message": "Run cancellation was requested.",
                        },
                    )
                ],
            )
        return run

    def resume_run(self, run_id, current_user: User):
        """Resume one interrupted run by restarting the persisted runtime session."""
        run = self.reconcile_run_entity(self._get_owned_run(run_id, current_user))
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
        transition_fields: dict[str, object] = {
            "status": RunStatus.RESUMING.value,
            "error_message": None,
        }
        if run.started_at is None:
            transition_fields["started_at"] = run.created_at

        run = self.state_service.update_run(
            run,
            fields=transition_fields,
            events=[
                RunEventSpec(
                    event_type=RunEventType.STATUS,
                    payload={
                        "status": RunStatus.RESUMING.value,
                        "message": (
                            f"Resuming the persisted {runtime_label} session after "
                            "host interruption."
                        ),
                    },
                ),
                RunEventSpec(
                    event_type=RunEventType.NOTE,
                    payload={
                        "kind": f"{runtime_event_prefix}_resume_requested",
                        "message": "Resume was requested from the interrupted run state.",
                        "runtime_session_id": persisted_runtime_session_id,
                        "codex_session_id": run.codex_session_id,
                        "claude_session_id": run.claude_session_id,
                    },
                ),
            ],
        )

        try:
            session = adapter.resume_session(str(run.id))
        except RuntimeAdapterError as exc:
            run = self.state_service.update_run(
                run,
                fields={
                    "status": RunStatus.INTERRUPTED.value,
                    "error_message": exc.detail,
                    "finished_at": run.finished_at,
                },
                events=[
                    RunEventSpec(
                        event_type=RunEventType.NOTE,
                        payload={
                            "kind": f"{runtime_event_prefix}_resume_failed",
                            "message": exc.detail,
                            "runtime_session_id": persisted_runtime_session_id,
                        },
                    )
                ],
            )
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

        return self.state_service.update_run(
            run,
            fields={
                **self._build_run_session_fields(session),
                "status": RunStatus.RESUMING.value,
                "error_message": None,
                "finished_at": None,
            },
            events=[
                RunEventSpec(
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
            ],
        )

    def get_terminal_session(self, run_id, current_user: User) -> TerminalSessionRead:
        """Return current host-side terminal session for one run."""
        run = self._get_owned_run(run_id, current_user)
        adapter = self._get_runtime_adapter(run.runtime_target)
        try:
            session = adapter.get_session(str(run.id))
        except RuntimeAdapterError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
        return adapter.normalize_terminal_session(session)

    def get_terminal_events(
        self,
        run_id,
        *,
        offset: int,
        current_user: User,
    ) -> TerminalSessionEventsResponse:
        """Return incremental terminal output for one run."""
        run = self._get_owned_run(run_id, current_user)
        adapter = self._get_runtime_adapter(run.runtime_target)
        try:
            events = adapter.get_events(str(run.id), offset=offset)
        except RuntimeAdapterError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
        return adapter.normalize_terminal_events(events)

    def _append_event(
        self,
        *,
        run_id,
        event_type: RunEventType,
        payload: dict[str, object] | None,
    ) -> None:
        """Persist one run event."""
        self.state_service.append_event(run_id=run_id, event_type=event_type, payload=payload)

    def _fail_run(self, run, *, detail: str):
        """Persist failed run state and expose the updated run object."""
        return self.state_service.fail_run(run, detail=detail)

    def _transition_run(self, run, *, status_value: RunStatus, message: str):
        """Persist one run status transition and emit a matching event."""
        return self.state_service.transition_run(run, status_value=status_value, message=message)

    def _append_materialization_audit_event(self, *, run_id, adapter, files) -> None:
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
    def _find_workspace_file_content(files, path: str) -> str:
        """Return one materialized file body by path."""
        for item in files:
            if item.path == path:
                return item.content
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Materialized workspace is missing `{path}`.",
        )

    def _build_workspace_files(self, **kwargs):
        """Delegate workspace materialization to the dedicated materializer service."""
        return self.workspace_materializer.build_workspace_files(**kwargs)

    @classmethod
    def _build_task_markdown(cls, **kwargs) -> str:
        """Preserve the legacy helper API for tests and call sites."""
        return RunWorkspaceMaterializer.build_task_markdown(**kwargs)

    @classmethod
    def _build_runtime_finalize_script(cls, **kwargs) -> str:
        """Preserve the legacy helper API for tests and call sites."""
        return RunWorkspaceMaterializer.render_finalize_script(**kwargs)

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

    def _get_runtime_adapter(self, runtime_target: str):
        """Return one registered runtime adapter or raise a normalized HTTP error."""
        return self.session_sync_service.get_runtime_adapter(runtime_target)

    def _build_run_session_fields(self, session):
        """Return run fields that mirror host-side runtime session metadata."""
        return self.session_sync_service.build_run_session_fields(session)

    @staticmethod
    def _parse_terminal_timestamp(value: str | None) -> datetime | None:
        """Parse one host-side UTC timestamp emitted in terminal/session payloads."""
        return RunSessionSyncService.parse_terminal_timestamp(value)

    def _sync_run_with_runtime_session(self, run):
        """Reconcile DB run state with host-side runtime session state when needed."""
        return self.session_sync_service.reconcile_run(run)

    def _finalize_completed_run(self, run, session, *, skip_prepare_transition: bool = False):
        """Conclude one completed runtime session from the observed workspace delivery state."""
        return self.session_sync_service.finalize_completed_run(
            run,
            session,
            skip_prepare_transition=skip_prepare_transition,
        )

    def _resolve_runtime_managed_workspace_outcome(self, run, *, summary_text: str | None):
        """Conclude one run strictly from runtime-managed workspace delivery state."""
        return self.session_sync_service.resolve_runtime_managed_workspace_outcome(
            run,
            summary_text=summary_text,
        )

    def _build_run_report(self, run):
        """Build a phase-oriented run report from structured events and workspace metadata."""
        return self.report_service.build_run_report(run)

    def _build_commit_message(self, run) -> str:
        """Return a deterministic git commit message for one finalized run."""
        return self.workspace_materializer.build_commit_message(run)

    @staticmethod
    def _build_pr_title(run) -> str:
        """Return a stable draft PR title for one run."""
        return RunWorkspaceMaterializer.build_pr_title(run)

    @staticmethod
    def _build_pr_body(run) -> str:
        """Return a concise PR body describing the automated run context."""
        return RunWorkspaceMaterializer.build_pr_body(run)

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

    @staticmethod
    def _ensure_owner(owner_id, current_user_id) -> None:
        """Require current user to own the requested run."""
        if owner_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the run creator can access this run.",
            )

    def _get_owned_run(self, run_id, current_user: User):
        """Load one run and require the current user to own it."""
        run = self.run_repository.get_by_id(run_id)
        if run is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
        self._ensure_owner(run.created_by, current_user.id)
        return run
