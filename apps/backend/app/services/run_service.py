"""Use-case orchestration for run preparation and materialization."""

from __future__ import annotations

import json
import re
import tomllib
from datetime import UTC, datetime
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import ZipFile

from fastapi import HTTPException, status

from app.models.export_job import ExportEntityType, RuntimeTarget
from app.models.run import RunEventType, RunStatus
from app.models.team import TeamStatus
from app.models.user import User
from app.repositories.run import RunRepository
from app.repositories.team import TeamRepository
from app.schemas.codex import CodexSessionEventsResponse, CodexSessionRead, CodexSessionStart
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
from app.schemas.workspace import (
    WorkspaceCommandsRun,
    WorkspaceCommandsRunResponse,
    WorkspaceCommit,
    WorkspaceExecutionConfigRead,
    WorkspaceFileWrite,
    WorkspaceMaterialize,
    WorkspacePrepare,
    WorkspacePullRequestCreate,
    WorkspaceRead,
)
from app.services.codex_proxy_service import CodexProxyService, CodexProxyServiceError
from app.services.export_service import ExportService
from app.services.github_proxy_service import GitHubProxyService, GitHubProxyServiceError
from app.services.host_execution_service import HostExecutionReadinessService
from app.services.workspace_proxy_service import WorkspaceProxyService, WorkspaceProxyServiceError


class RunService:
    """Create and inspect local-first Codex runs."""

    _SKILL_PATH_PATTERN = re.compile(r"\.codex/skills/([^/\s]+)/SKILL\.md")
    _AGENT_CONFIG_PATH_PATTERN = re.compile(r"\.codex/agents/([^/\s]+)\.toml")
    _SKILL_MENTION_PATTERN = re.compile(r"(?:skill|скилл)[^`]*`([^`]+)`", re.IGNORECASE)
    _BACKTICK_SLUG_PATTERN = re.compile(r"`([a-z0-9][a-z0-9_-]{1,80})`", re.IGNORECASE)
    _ROLE_PROMPT_PATTERN = re.compile(
        r"^\s*Role:\s*([a-z0-9][a-z0-9_-]{1,80})\.?\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    _MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\([^)]+\)")
    _SUBAGENT_SIGNAL_PATTERN = re.compile(
        r"\b(spawn(?:ed|ing)?|launch(?:ed|ing)?|delegat(?:e|ed|ing)|handoff|hand off)\b"
        r"[^.\n\r]{0,120}\b(subagent|sub-agent|child agent|agent)\b",
        re.IGNORECASE,
    )
    _AGENT_RESULT_SECTION_PATTERN = re.compile(
        r"(?:^|\n)(?:2\.\s*Risks or findings|3\.\s*Proposed changes|"
        r"2\.\s*Риски или находки|3\.\s*Предлагаемые изменения)\s*(.*?)(?=\n\d+\.\s|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    _READY_MESSAGE = (
        "Workspace is prepared and `.codex` plus `TASK.md` are materialized. "
        "Codex PTY execution is the next layer."
    )

    def __init__(
        self,
        run_repository: RunRepository,
        team_repository: TeamRepository,
        export_service: ExportService,
        workspace_proxy_service: WorkspaceProxyService,
        codex_proxy_service: CodexProxyService,
        github_proxy_service: GitHubProxyService,
        readiness_service: HostExecutionReadinessService,
    ) -> None:
        self.run_repository = run_repository
        self.team_repository = team_repository
        self.export_service = export_service
        self.workspace_proxy_service = workspace_proxy_service
        self.codex_proxy_service = codex_proxy_service
        self.github_proxy_service = github_proxy_service
        self.readiness_service = readiness_service

    def create_run(self, payload: RunCreate, current_user: User):
        """Create a run, prepare its workspace, and materialize Codex inputs."""
        readiness = self.readiness_service.build_readiness()
        if not readiness.effective_ready:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Local execution is not ready. Open diagnostics, fix `git`/`gh`/`codex`, "
                    "and retry the run."
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
            runtime_target=RuntimeTarget.CODEX.value,
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
            runtime_config_json=self._build_runtime_config(payload.codex),
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
            execution_config = self.workspace_proxy_service.get_execution_config(workspace.id)
            if execution_config.source_path:
                self._append_event(
                    run_id=run.id,
                    event_type=RunEventType.NOTE,
                    payload={
                        "message": (
                            f"Loaded repo execution config from `{execution_config.source_path}`."
                        ),
                        "config": execution_config.model_dump(),
                    },
                )
            if execution_config.setup_commands:
                run = self._transition_run(
                    run,
                    status_value=RunStatus.RUNNING_SETUP,
                    message="Running repo setup commands before starting Codex.",
                )
                setup_result = self.workspace_proxy_service.run_commands(
                    workspace.id,
                    WorkspaceCommandsRun(
                        commands=execution_config.setup_commands,
                        working_directory=execution_config.setup_working_directory,
                        label="repo-setup",
                    ),
                )
                self._append_command_results_event(
                    run_id=run.id,
                    command_results=setup_result,
                    success_message="Repo setup commands completed successfully.",
                )
                if not setup_result.success:
                    return self._fail_run(
                        run,
                        detail=self._build_command_failure_detail(
                            phase="repo setup",
                            result=setup_result,
                        ),
                    )
                workspace = self.workspace_proxy_service.get_workspace(workspace.id)
                if workspace.has_changes:
                    changed_files = ", ".join(workspace.changed_files[:10]) or "unknown files"
                    return self._fail_run(
                        run,
                        detail=(
                            "Repo setup commands modified tracked files before Codex execution. "
                            f"Review `{execution_config.source_path}` and keep setup read-only. "
                            f"Changed files: {changed_files}."
                        ),
                    )

            run = self._transition_run(
                run,
                status_value=RunStatus.MATERIALIZING_TEAM,
                message="Writing `.codex` bundle and `TASK.md` into the workspace.",
            )
            workspace_files = self._build_workspace_files(
                team_slug=team.slug,
                team_startup_prompt=team.startup_prompt,
                payload=payload,
                repo_full_name=repo.full_name,
                base_branch=workspace.base_branch,
                working_branch=workspace.working_branch,
                execution_config=execution_config,
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
                files=workspace_files,
            )
            task_markdown = self._find_workspace_file_content(workspace_files, "TASK.md")
            run = self._transition_run(
                run,
                status_value=RunStatus.STARTING_CODEX,
                message="Starting host-side Codex session.",
            )
            session = self.codex_proxy_service.start_session(
                payload=self._build_codex_session_payload(
                    run_id=str(run.id),
                    workspace_id=workspace.id,
                    task_markdown=task_markdown,
                    codex_options=payload.codex,
                )
            )
            run = self.run_repository.update(
                run,
                fields=self._build_run_session_fields(session),
            )
            run = self._transition_run(
                run,
                status_value=RunStatus.RUNNING,
                message="Codex session is running in the prepared workspace.",
            )
            return run
        except (WorkspaceProxyServiceError, GitHubProxyServiceError, CodexProxyServiceError) as exc:
            return self._fail_run(run, detail=exc.detail)
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
        items = [self._sync_run_with_codex_session(item) for item in items]
        return RunListResponse(items=items, total=total, limit=limit, offset=offset)

    def get_run(self, run_id, current_user: User):
        """Return one run owned by the current user."""
        run = self.run_repository.get_by_id(run_id)
        if run is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
        self._ensure_owner(run.created_by, current_user.id)
        run = self._sync_run_with_codex_session(run)
        run.run_report = self._build_run_report(run)
        return run

    def list_run_events(self, run_id, current_user: User) -> RunEventListResponse:
        """Return ordered run events for one run owned by the current user."""
        run = self.get_run(run_id, current_user)
        items = self.run_repository.list_events(run_id=run.id)
        return RunEventListResponse(items=items, total=len(items))

    def cancel_run(self, run_id, current_user: User):
        """Cancel one running host-side Codex session."""
        run = self.get_run(run_id, current_user)
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
            session = self.codex_proxy_service.cancel_session(str(run.id))
        except CodexProxyServiceError as exc:
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
        """Resume one interrupted run by restarting Codex from the persisted session id."""
        run = self.get_run(run_id, current_user)
        if run.status != RunStatus.INTERRUPTED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only interrupted runs can be resumed.",
            )
        if not run.workspace_id or not run.codex_session_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Run is missing workspace or Codex session metadata required for resume.",
            )

        run = self._transition_run(
            run,
            status_value=RunStatus.RESUMING,
            message="Resuming the persisted Codex session after host interruption.",
        )
        self._append_event(
            run_id=run.id,
            event_type=RunEventType.NOTE,
            payload={
                "kind": "codex_resume_requested",
                "message": "Resume was requested from the interrupted run state.",
                "codex_session_id": run.codex_session_id,
            },
        )

        try:
            session = self.codex_proxy_service.resume_session(str(run.id))
        except CodexProxyServiceError as exc:
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
                    "kind": "codex_resume_failed",
                    "message": exc.detail,
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
                "kind": "codex_resume_started",
                "message": "Host executor started `codex exec resume` for this run.",
                "resume_attempt_count": session.resume_attempt_count,
                "codex_session_id": session.codex_session_id,
            },
        )
        return run

    def rerun_run(self, run_id, current_user: User):
        """Create a fresh run from one finished run context."""
        run = self.get_run(run_id, current_user)
        if run.status not in {
            RunStatus.COMPLETED.value,
            RunStatus.FAILED.value,
            RunStatus.CANCELLED.value,
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only completed, failed, or cancelled runs can be run again. "
                    "Use resume for interrupted runs."
                ),
            )

        rerun = self.create_run(self._build_rerun_payload(run), current_user)
        self._append_event(
            run_id=rerun.id,
            event_type=RunEventType.NOTE,
            payload={
                "kind": "rerun",
                "message": "This run was created from an earlier run context.",
                "source_run_id": str(run.id),
            },
        )
        return rerun

    def get_terminal_session(self, run_id, current_user: User) -> CodexSessionRead:
        """Return current host-side terminal session for one run."""
        run = self.get_run(run_id, current_user)
        try:
            return self.codex_proxy_service.get_session(str(run.id))
        except CodexProxyServiceError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    def get_terminal_events(
        self,
        run_id,
        *,
        offset: int,
        current_user: User,
    ) -> CodexSessionEventsResponse:
        """Return incremental terminal output for one run."""
        run = self.get_run(run_id, current_user)
        try:
            return self.codex_proxy_service.get_events(str(run.id), offset=offset)
        except CodexProxyServiceError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

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
        team_slug: str,
        team_startup_prompt: str | None,
        payload: RunCreate,
        repo_full_name: str,
        base_branch: str,
        working_branch: str,
        execution_config: WorkspaceExecutionConfigRead,
        issue_title: str | None,
        issue_number: int | None,
        issue_url: str | None,
        issue_body: str | None,
    ) -> list[WorkspaceFileWrite]:
        """Return text files that should be written into the prepared workspace."""
        _, bundle_bytes, _ = self.export_service.build_download_artifact(
            entity_type=ExportEntityType.TEAM,
            slug=team_slug,
            runtime_target=RuntimeTarget.CODEX.value,
            codex_options=payload.codex,
        )
        files = self._extract_text_files_from_zip(bundle_bytes)
        files["TASK.md"] = self._build_task_markdown(
            payload=payload,
            team_startup_prompt=team_startup_prompt,
            repo_full_name=repo_full_name,
            base_branch=base_branch,
            working_branch=working_branch,
            execution_config=execution_config,
            issue_title=issue_title,
            issue_number=issue_number,
            issue_url=issue_url,
            issue_body=issue_body,
        )
        return [
            WorkspaceFileWrite(path=path, content=content)
            for path, content in sorted(files.items())
        ]

    @staticmethod
    def _extract_text_files_from_zip(content: bytes) -> dict[str, str]:
        """Extract UTF-8 text files from a generated bundle zip."""
        files: dict[str, str] = {}
        with ZipFile(BytesIO(content)) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                normalized = PurePosixPath(member.filename)
                if normalized.is_absolute() or any(
                    part in {"", ".", ".."} for part in normalized.parts
                ):
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Generated export bundle contains an invalid file path.",
                    )
                files[str(normalized)] = archive.read(member).decode("utf-8")
        return files

    @classmethod
    def _build_task_markdown(
        cls,
        *,
        payload: RunCreate,
        team_startup_prompt: str | None,
        repo_full_name: str,
        base_branch: str,
        working_branch: str,
        execution_config: WorkspaceExecutionConfigRead,
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
                    "## Codex Startup Prompt",
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
        if execution_config.source_path:
            lines.extend(
                [
                    "",
                    "## Repo Execution Contract",
                    f"- Source: `{execution_config.source_path}`",
                    f"- Preferred working directory: `{execution_config.run_working_directory}`",
                ]
            )
            if execution_config.setup_commands:
                lines.extend(["", "### Repo Setup Commands"])
                lines.extend(f"- `{command}`" for command in execution_config.setup_commands)
            if execution_config.check_commands:
                lines.extend(["", "### Repo Check Commands"])
                lines.extend(f"- `{command}`" for command in execution_config.check_commands)
        lines.extend(
            [
                "",
                "## Constraints",
                "- Keep changes scoped to the requested task.",
                "- Prefer minimal, reviewable edits over broad rewrites.",
                (
                    "- Prefer repo execution commands from the config above instead of "
                    "guessing project bootstrap."
                ),
                "- Run the configured repo checks before finishing work.",
                "- Avoid modifying unrelated files.",
            ]
        )
        return "\n".join(lines).strip() + "\n"

    @staticmethod
    def _build_runtime_config(codex: CodexExportOptions | None) -> dict[str, object]:
        """Persist selected runtime parameters for future execution steps."""
        config: dict[str, object] = {"runtime_target": RuntimeTarget.CODEX.value}
        if codex is not None:
            config["codex"] = codex.model_dump(exclude_none=True)
        return config

    @staticmethod
    def _build_codex_session_payload(
        *,
        run_id: str,
        workspace_id: str,
        task_markdown: str,
        codex_options: CodexExportOptions | None,
    ) -> CodexSessionStart:
        """Build payload sent to the host executor for Codex session startup."""
        return CodexSessionStart(
            run_id=run_id,
            workspace_id=workspace_id,
            prompt_text=task_markdown,
            model=codex_options.model if codex_options is not None else None,
            model_reasoning_effort=(
                codex_options.model_reasoning_effort if codex_options is not None else None
            ),
            sandbox_mode=(
                codex_options.sandbox_mode if codex_options is not None else "workspace-write"
            ),
        )

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
    def _build_rerun_payload(run) -> RunCreate:
        """Reconstruct one fresh run payload from persisted run context."""
        codex_config = None
        if isinstance(run.runtime_config_json, dict):
            raw_codex = run.runtime_config_json.get("codex")
            if isinstance(raw_codex, dict):
                codex_config = CodexExportOptions.model_validate(raw_codex)

        return RunCreate(
            team_slug=run.team_slug,
            repo_owner=run.repo_owner,
            repo_name=run.repo_name,
            base_branch=run.base_branch,
            issue_number=run.issue_number,
            task_text=run.task_text,
            title=run.title,
            summary=run.summary,
            codex=codex_config,
        )

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

    def _append_command_results_event(
        self,
        *,
        run_id,
        command_results: WorkspaceCommandsRunResponse,
        success_message: str,
    ) -> None:
        """Persist one note event that summarizes repo-scoped command execution."""
        items = [
            {
                "command": item.command,
                "exit_code": item.exit_code,
                "succeeded": item.succeeded,
                "output": item.output,
                "started_at": item.started_at,
                "finished_at": item.finished_at,
            }
            for item in command_results.items
        ]
        message = success_message
        if not command_results.success and command_results.failed_command:
            message = f"Command batch failed on `{command_results.failed_command}`."
        self._append_event(
            run_id=run_id,
            event_type=RunEventType.NOTE,
            payload={
                "message": message,
                "label": command_results.label,
                "working_directory": command_results.working_directory,
                "success": command_results.success,
                "items": items,
            },
        )

    def _append_materialization_audit_event(
        self,
        *,
        run_id,
        files: list[WorkspaceFileWrite],
    ) -> None:
        """Persist one snapshot of the materialized Codex bundle before cleanup."""
        file_map = {item.path: item.content for item in files}
        config_toml = file_map.get(".codex/config.toml")
        task_markdown = file_map.get("TASK.md")
        configured_agents = self._extract_configured_agents(config_toml)
        multi_agent_enabled = self._config_enables_multi_agent(config_toml)
        agent_configs = [
            {
                "key": path.rsplit("/", maxsplit=1)[-1].removesuffix(".toml"),
                "path": path,
                "content": content,
            }
            for path, content in sorted(file_map.items())
            if path.startswith(".codex/agents/") and path.endswith(".toml")
        ]

        if multi_agent_enabled:
            message = (
                f"Materialized Codex multi-agent bundle with "
                f"{len(configured_agents)} configured role(s)."
            )
        else:
            message = "Materialized Codex bundle for the run workspace."

        self._append_event(
            run_id=run_id,
            event_type=RunEventType.NOTE,
            payload={
                "kind": "codex_bundle",
                "message": message,
                "multi_agent_enabled": multi_agent_enabled,
                "configured_agents": configured_agents,
                "config_toml": config_toml,
                "agent_configs": agent_configs,
                "task_markdown": task_markdown,
            },
        )

    @classmethod
    def _extract_configured_agents(cls, config_toml: str | None) -> list[str]:
        """Return configured Codex agent keys from one materialized config."""
        if not config_toml:
            return []
        try:
            parsed = tomllib.loads(config_toml)
        except tomllib.TOMLDecodeError:
            return []
        agents = parsed.get("agents")
        if not isinstance(agents, dict):
            return []
        return [str(key) for key in agents.keys()]

    @staticmethod
    def _config_enables_multi_agent(config_toml: str | None) -> bool:
        """Return whether one materialized config explicitly enables multi-agent mode."""
        if not config_toml:
            return False
        try:
            parsed = tomllib.loads(config_toml)
        except tomllib.TOMLDecodeError:
            return False
        features = parsed.get("features")
        return isinstance(features, dict) and bool(features.get("multi_agent"))

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

    @staticmethod
    def _build_command_failure_detail(
        *,
        phase: str,
        result: WorkspaceCommandsRunResponse,
    ) -> str:
        """Return readable failure detail for a failed repo command batch."""
        if not result.items:
            return f"{phase.capitalize()} failed before any command completed."

        failed_item = next((item for item in result.items if not item.succeeded), result.items[-1])
        detail = failed_item.output.strip()
        if detail:
            return (
                f"{phase.capitalize()} failed on `{failed_item.command}` "
                f"(exit code {failed_item.exit_code}).\n\n{detail[:1200]}"
            )
        return (
            f"{phase.capitalize()} failed on `{failed_item.command}` "
            f"(exit code {failed_item.exit_code})."
        )

    def _sync_run_with_codex_session(self, run):
        """Reconcile DB run state with host-side Codex session state when needed."""
        if run.status not in {
            RunStatus.STARTING_CODEX.value,
            RunStatus.RUNNING.value,
            RunStatus.RESUMING.value,
        }:
            return run

        try:
            session = self.codex_proxy_service.get_session(str(run.id))
        except CodexProxyServiceError as exc:
            if exc.status_code == 404:
                return self._fail_run(
                    run,
                    detail=(
                        "Host-side Codex session state was lost. "
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
                        "message": "Codex session resumed and is running again.",
                    },
                )
                self._append_event(
                    run_id=updated.id,
                    event_type=RunEventType.NOTE,
                    payload={
                        "kind": (
                            "codex_auto_resume_completed"
                            if session.recovered_from_restart
                            else "codex_resume_completed"
                        ),
                        "message": (
                            "Automatic recovery completed and terminal output is live again."
                            if session.recovered_from_restart
                            else "Resume completed and terminal output is live again."
                        ),
                        "resume_attempt_count": session.resume_attempt_count,
                    },
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
                    payload={
                        "kind": "codex_auto_resume_completed",
                        "message": (
                            "Host executor recovered the Codex session automatically "
                            "before the next poll and terminal output is live again."
                        ),
                        "resume_attempt_count": session.resume_attempt_count,
                    },
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
                        "message": (
                            "Host executor restarted and automatic Codex recovery "
                            "is in progress."
                        ),
                    },
                )
                self._append_event(
                    run_id=updated.id,
                    event_type=RunEventType.NOTE,
                    payload={
                        "kind": "codex_auto_resume_started",
                        "message": (
                            "Host executor restarted and semantic resume started automatically "
                            "from the persisted Codex session."
                        ),
                        "resume_attempt_count": session.resume_attempt_count,
                        "codex_session_id": session.codex_session_id,
                    },
                )
            return updated

        self._append_codex_terminal_audit_event(run_id=run.id)

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
                    "message": session.error_message or "Codex session was interrupted.",
                },
            )
            self._append_event(
                run_id=updated.id,
                event_type=RunEventType.NOTE,
                payload={
                    "kind": "codex_session_interrupted",
                    "message": session.error_message or "Codex session was interrupted.",
                    "resumable": session.resumable,
                    "codex_session_id": session.codex_session_id,
                    "resume_attempt_count": session.resume_attempt_count,
                },
            )
            if session.resumable:
                self._append_event(
                    run_id=updated.id,
                    event_type=RunEventType.NOTE,
                    payload={
                        "kind": "codex_resume_available",
                        "message": (
                            "The interrupted Codex session can be resumed "
                            "from the same run."
                        ),
                        "codex_session_id": session.codex_session_id,
                    },
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
                    "message": "Codex session was cancelled.",
                },
            )
            return updated

        updated = self.run_repository.update(
            run,
            fields={
                **self._build_run_session_fields(session),
                "status": RunStatus.FAILED.value,
                "error_message": session.error_message or "Codex session failed.",
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

    @staticmethod
    def _build_run_session_fields(session: CodexSessionRead) -> dict[str, object]:
        """Return run fields that mirror host-side Codex session metadata."""
        fields: dict[str, object] = {
            "codex_session_id": session.codex_session_id,
            "transport_kind": session.transport_kind,
            "transport_ref": session.transport_ref,
            "resume_attempt_count": session.resume_attempt_count,
        }
        interrupted_at = RunService._parse_terminal_timestamp(session.interrupted_at)
        if interrupted_at is not None:
            fields["interrupted_at"] = interrupted_at
        return fields

    @staticmethod
    def _parse_terminal_timestamp(value: str | None) -> datetime | None:
        """Parse one host-side UTC timestamp emitted in terminal/session payloads."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _append_codex_terminal_audit_event(self, *, run_id) -> None:
        """Persist one execution-trace snapshot derived from Codex terminal JSON."""
        try:
            session_events = self.codex_proxy_service.get_events(str(run_id), offset=0)
        except CodexProxyServiceError as exc:
            self._append_event(
                run_id=run_id,
                event_type=RunEventType.NOTE,
                payload={
                    "kind": "codex_execution_trace",
                    "message": "Codex terminal trace could not be captured.",
                    "trace_capture_error": exc.detail,
                },
            )
            return

        trace_payload = self._build_codex_terminal_audit_payload(session_events)
        self._append_event(
            run_id=run_id,
            event_type=RunEventType.NOTE,
            payload=trace_payload,
        )

    @classmethod
    def _build_codex_terminal_audit_payload(
        cls,
        session_events: CodexSessionEventsResponse,
    ) -> dict[str, object]:
        """Summarize Codex terminal output into one audit-friendly payload."""
        skill_reads: set[str] = set()
        skill_mentions: set[str] = set()
        agent_config_reads: set[str] = set()
        delegation_markers: list[str] = []
        thread_ids: list[str] = []
        spawned_agents_by_thread: dict[str, dict[str, str | None]] = {}
        item_type_counts: dict[str, int] = {}

        for line in cls._iter_terminal_lines(session_events):
            if "WARN codex_core::file_watcher: failed to unwatch" in line:
                continue
            if not line.strip():
                continue

            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue

            if payload.get("type") == "thread.started":
                thread_id = payload.get("thread_id")
                if isinstance(thread_id, str) and thread_id.strip():
                    thread_ids.append(thread_id.strip())

            item = payload.get("item")
            if not isinstance(item, dict):
                continue

            item_type = item.get("type")
            if not isinstance(item_type, str):
                continue
            item_type_counts[item_type] = item_type_counts.get(item_type, 0) + 1

            if item_type == "command_execution":
                for value in (item.get("command"), item.get("aggregated_output")):
                    if not isinstance(value, str):
                        continue
                    skill_reads.update(cls._SKILL_PATH_PATTERN.findall(value))
                    agent_config_reads.update(cls._AGENT_CONFIG_PATH_PATTERN.findall(value))
                continue

            if item_type == "agent_message":
                text = item.get("text")
                if not isinstance(text, str):
                    continue
                skill_mentions.update(
                    match.group(1) for match in cls._SKILL_MENTION_PATTERN.finditer(text)
                )
                skill_mentions.update(
                    match.group(1) for match in cls._BACKTICK_SLUG_PATTERN.finditer(text)
                )
                if cls._SUBAGENT_SIGNAL_PATTERN.search(text):
                    delegation_markers.append(cls._truncate_audit_line(text))
                continue

            if item_type != "collab_tool_call":
                continue

            tool = item.get("tool")
            receiver_thread_ids = cls._coerce_receiver_thread_ids(item.get("receiver_thread_ids"))
            if not receiver_thread_ids:
                continue

            if tool == "spawn_agent":
                role = cls._extract_role_from_prompt(item.get("prompt"))
                cls._merge_spawned_agent_states(
                    spawned_agents_by_thread=spawned_agents_by_thread,
                    receiver_thread_ids=receiver_thread_ids,
                    role=role,
                    agents_states=item.get("agents_states"),
                )
                continue

            if tool in {"wait", "close_agent"}:
                cls._merge_spawned_agent_states(
                    spawned_agents_by_thread=spawned_agents_by_thread,
                    receiver_thread_ids=receiver_thread_ids,
                    role=None,
                    agents_states=item.get("agents_states"),
                )

        unique_thread_ids = cls._dedupe_preserve_order(thread_ids)
        spawned_agents = list(spawned_agents_by_thread.values())
        spawned_thread_ids = [
            thread_id
            for agent in spawned_agents
            if isinstance(thread_id := agent.get("thread_id"), str) and thread_id
        ]
        additional_thread_ids = cls._dedupe_preserve_order(
            [*unique_thread_ids[1:], *spawned_thread_ids]
        )
        unique_delegation_markers = cls._dedupe_preserve_order(delegation_markers)
        unique_skill_refs = cls._dedupe_preserve_order(
            [*sorted(skill_reads), *sorted(skill_mentions)]
        )
        unique_agent_config_reads = cls._dedupe_preserve_order(sorted(agent_config_reads))

        if spawned_agents:
            signal_level = "confirmed"
            message = (
                f"Observed {len(spawned_agents)} spawned agent(s) via collaboration tool calls; "
                "this is confirmed sub-agent execution."
            )
        elif additional_thread_ids:
            signal_level = "confirmed"
            message = (
                f"Observed {len(additional_thread_ids)} additional Codex thread id(s); "
                "this is strong evidence of sub-agent execution."
            )
        elif unique_delegation_markers:
            signal_level = "confirmed"
            message = (
                f"Observed {len(unique_delegation_markers)} explicit sub-agent signal(s) "
                "in Codex agent messages."
            )
        elif unique_agent_config_reads:
            signal_level = "possible"
            message = (
                "Codex read agent config files during execution, "
                "but no confirmed sub-agent spawn signals were captured."
            )
        elif unique_skill_refs:
            signal_level = "none"
            message = (
                "Codex referenced skills during execution, "
                "but no multi-agent signals were captured."
            )
        else:
            signal_level = "none"
            message = (
                "No sub-agent execution signals were captured in the Codex terminal output."
            )

        return {
            "kind": "codex_execution_trace",
            "message": message,
            "multi_agent_signal_level": signal_level,
            "chunk_count": len(session_events.items),
            "thread_ids": unique_thread_ids[:10],
            "additional_thread_ids": additional_thread_ids[:10],
            "spawned_agents": spawned_agents[:10],
            "skill_refs": unique_skill_refs,
            "agent_config_reads": unique_agent_config_reads,
            "delegation_markers": unique_delegation_markers[:5],
            "item_type_counts": item_type_counts,
        }

    @staticmethod
    def _iter_terminal_lines(session_events: CodexSessionEventsResponse) -> list[str]:
        """Return complete terminal lines reconstructed from raw chunk output."""
        lines: list[str] = []
        buffer = ""
        for item in session_events.items:
            combined = f"{buffer}{item.text}"
            normalized = combined.replace("\r\n", "\n")
            parts = normalized.split("\n")
            buffer = parts.pop() if parts else normalized
            lines.extend(parts)
        if buffer.strip():
            lines.append(buffer)
        return lines

    @staticmethod
    def _truncate_audit_line(value: str) -> str:
        """Return a compact, single-line preview for audit payloads."""
        normalized = " ".join(value.strip().split())
        return normalized[:240]

    @classmethod
    def _extract_role_from_prompt(cls, value: object) -> str | None:
        """Return one role slug from a spawned-agent prompt when present."""
        if not isinstance(value, str):
            return None
        match = cls._ROLE_PROMPT_PATTERN.search(value)
        if not match:
            return None
        role = match.group(1).strip()
        return role or None

    @staticmethod
    def _coerce_receiver_thread_ids(value: object) -> list[str]:
        """Return one stable list of receiver thread ids."""
        if not isinstance(value, list):
            return []
        thread_ids: list[str] = []
        for item in value:
            if not isinstance(item, str):
                continue
            normalized = item.strip()
            if not normalized:
                continue
            thread_ids.append(normalized)
        return thread_ids

    @classmethod
    def _merge_spawned_agent_states(
        cls,
        *,
        spawned_agents_by_thread: dict[str, dict[str, str | None]],
        receiver_thread_ids: list[str],
        role: str | None,
        agents_states: object,
    ) -> None:
        """Merge spawned-agent metadata from collab tool calls."""
        agent_state_map = agents_states if isinstance(agents_states, dict) else {}
        for thread_id in receiver_thread_ids:
            agent = spawned_agents_by_thread.setdefault(
                thread_id,
                {
                    "thread_id": thread_id,
                    "role": None,
                    "status": None,
                    "result_preview": None,
                },
            )
            if role and not agent.get("role"):
                agent["role"] = role

            state_payload = agent_state_map.get(thread_id)
            if not isinstance(state_payload, dict):
                continue
            status = state_payload.get("status")
            if isinstance(status, str) and status.strip():
                agent["status"] = status.strip()
            message = state_payload.get("message")
            if isinstance(message, str) and message.strip():
                agent["result_preview"] = cls._extract_agent_result_preview(message)

    @classmethod
    def _extract_agent_result_preview(cls, value: str) -> str:
        """Extract one compact, user-facing preview from a structured sub-agent report."""
        match = cls._AGENT_RESULT_SECTION_PATTERN.search(value)
        candidate = match.group(1) if match else value

        cleaned_lines: list[str] = []
        for raw_line in candidate.splitlines():
            normalized = " ".join(raw_line.strip().split())
            if not normalized:
                continue
            normalized = cls._MARKDOWN_LINK_PATTERN.sub(r"\1", normalized)
            if normalized.startswith("- "):
                normalized = normalized[2:].strip()
            cleaned_lines.append(normalized)

        compact = " ".join(cleaned_lines) if cleaned_lines else value
        return cls._truncate_audit_line(compact)

    @staticmethod
    def _dedupe_preserve_order(items: list[str]) -> list[str]:
        """Return one stable list with duplicates removed."""
        unique: list[str] = []
        seen: set[str] = set()
        for item in items:
            if not item or item in seen:
                continue
            seen.add(item)
            unique.append(item)
        return unique

    def _finalize_completed_run(self, run, session: CodexSessionRead):
        """Convert a completed Codex session into commit, push, and draft-PR artifacts."""
        if run.workspace_id is None:
            return self._fail_run(
                run,
                detail="Run is missing workspace metadata required for post-Codex finalization.",
            )

        try:
            run = self._transition_run(
                run,
                status_value=RunStatus.COMMITTING,
                message="Cleaning temporary `.codex` files and preparing a git commit.",
            )
            workspace = self.workspace_proxy_service.cleanup_workspace(run.workspace_id)
            execution_config = self.workspace_proxy_service.get_execution_config(run.workspace_id)

            if not workspace.has_changes:
                return self._complete_run(
                    run,
                    summary_text=session.summary_text,
                    message="Codex session completed with no repository changes to commit.",
                )

            if execution_config.check_commands:
                run = self._transition_run(
                    run,
                    status_value=RunStatus.RUNNING_CHECKS,
                    message="Running repo check commands before commit and push.",
                )
                check_result = self.workspace_proxy_service.run_commands(
                    run.workspace_id,
                    WorkspaceCommandsRun(
                        commands=execution_config.check_commands,
                        working_directory=execution_config.check_working_directory,
                        label="repo-checks",
                    ),
                )
                self._append_command_results_event(
                    run_id=run.id,
                    command_results=check_result,
                    success_message="Repo check commands completed successfully.",
                )
                if not check_result.success:
                    return self._fail_run(
                        run,
                        detail=self._build_command_failure_detail(
                            phase="repo checks",
                            result=check_result,
                        ),
                    )

            run = self._transition_run(
                run,
                status_value=RunStatus.COMMITTING,
                message="Creating a git commit from the Codex changes.",
            )
            workspace = self.workspace_proxy_service.commit_workspace(
                run.workspace_id,
                WorkspaceCommit(message=self._build_commit_message(run)),
            )
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
                message="Creating a draft pull request for the Codex changes.",
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
        """Persist final completed state after Codex and optional SCM post-processing."""
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

    @staticmethod
    def _build_commit_message(run) -> str:
        """Return a deterministic git commit message for one finalized run."""
        title = run.title.strip()
        if run.issue_number is not None:
            return f"chore(run): address #{run.issue_number} {title[:140]}".strip()
        return f"chore(run): apply codex changes for {title[:160]}".strip()

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

        phases: dict[str, RunReportPhaseRead] = {
            "preparation": RunReportPhaseRead(
                key="preparation",
                order=1,
                status="not_started",
                description="Workspace and task scaffolding preparation.",
            ),
            "setup": RunReportPhaseRead(
                key="setup",
                order=2,
                status="not_started",
                description="Repository setup commands from execution config.",
            ),
            "codex": RunReportPhaseRead(
                key="codex",
                order=3,
                status="not_started",
                description="Host-side Codex terminal execution.",
            ),
            "checks": RunReportPhaseRead(
                key="checks",
                order=4,
                status="not_started",
                description="Repository check commands before commit and push.",
            ),
            "git_pr": RunReportPhaseRead(
                key="git_pr",
                order=5,
                status="not_started",
                description="Commit, push, and draft pull request finalization.",
            ),
        }

        setup_available = False
        checks_available = False
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
                commands = payload.get("items")
                config = payload.get("config")

                if isinstance(config, dict):
                    setup_commands = config.get("setup_commands")
                    check_commands = config.get("check_commands")
                    setup_available = isinstance(setup_commands, list) and len(setup_commands) > 0
                    checks_available = isinstance(check_commands, list) and len(check_commands) > 0

                if label == "repo-setup":
                    phase = phases["setup"]
                    phase.first_event_at = phase.first_event_at or event.created_at
                    phase.last_event_at = event.created_at
                    phase.commands = self._parse_report_commands(commands)
                    setup_available = True
                if label == "repo-checks":
                    phase = phases["checks"]
                    phase.first_event_at = phase.first_event_at or event.created_at
                    phase.last_event_at = event.created_at
                    phase.commands = self._parse_report_commands(commands)
                    checks_available = True

        for key, phase in phases.items():
            phase.status = self._resolve_phase_status(
                phase_key=key,
                run_status=run.status,
                has_events=phase.first_event_at is not None,
                failure_phase=failure_phase,
                setup_available=setup_available,
                checks_available=checks_available,
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
            RunStatus.RUNNING_SETUP.value: "setup",
            RunStatus.STARTING_CODEX.value: "codex",
            RunStatus.RUNNING.value: "codex",
            RunStatus.INTERRUPTED.value: "codex",
            RunStatus.RESUMING.value: "codex",
            RunStatus.RUNNING_CHECKS.value: "checks",
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
        setup_available: bool,
        checks_available: bool,
    ) -> RunReportPhaseStatus:
        """Compute one report-phase status from run state and event history."""
        if phase_key == "setup" and not setup_available and not has_events:
            return "not_available"
        if phase_key == "checks" and not checks_available and not has_events:
            return "not_available"

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
            if has_events or phase_key in {"setup", "checks"}:
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
