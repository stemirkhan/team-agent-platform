"""Runtime-session reconciliation and post-run finalization."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status

from app.models.export_job import RuntimeTarget
from app.models.run import RunEventType, RunStatus
from app.services.run_state_service import RunEventSpec, RunStateService
from app.services.runtime_adapters import (
    BackendRuntimeAdapter,
    RuntimeAdapterError,
    RuntimeAdapterRegistry,
    RuntimeSessionRead,
)
from app.services.workspace_proxy_service import WorkspaceProxyService, WorkspaceProxyServiceError


class RunSessionSyncService:
    """Reconcile backend run state against host-side runtime sessions."""

    ACTIVE_RUN_STATUSES = (
        RunStatus.STARTING_RUNTIME.value,
        RunStatus.STARTING_CODEX.value,
        RunStatus.RUNNING.value,
        RunStatus.RESUMING.value,
        RunStatus.COMMITTING.value,
    )
    _RUNTIME_ACTIVE_STATUSES = (
        RunStatus.STARTING_RUNTIME.value,
        RunStatus.STARTING_CODEX.value,
        RunStatus.RUNNING.value,
        RunStatus.RESUMING.value,
    )

    def __init__(
        self,
        *,
        run_repository,
        workspace_proxy_service: WorkspaceProxyService,
        runtime_adapters: RuntimeAdapterRegistry,
        state_service: RunStateService,
    ) -> None:
        self.run_repository = run_repository
        self.workspace_proxy_service = workspace_proxy_service
        self.runtime_adapters = runtime_adapters
        self.state_service = state_service

    def get_runtime_adapter(self, runtime_target: str) -> BackendRuntimeAdapter:
        """Return one registered runtime adapter or raise a normalized HTTP error."""
        adapter = self.runtime_adapters.get(runtime_target)
        if adapter is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Runtime '{runtime_target}' runs are not implemented yet.",
            )
        return adapter

    def reconcile_run(self, run):
        """Reconcile DB run state with host-side runtime session state when needed."""
        if run.status not in self.ACTIVE_RUN_STATUSES:
            return run

        adapter = self.get_runtime_adapter(run.runtime_target)
        try:
            session = adapter.get_session(str(run.id))
        except RuntimeAdapterError as exc:
            if exc.status_code == 404:
                return self.state_service.fail_run(
                    run,
                    detail=(
                        f"Host-side {adapter.label} session state was lost. "
                        "This usually means the host executor restarted during the run. "
                        "Relaunch the run."
                    ),
                )
            return self.state_service.fail_run(run, detail=exc.detail)

        if session.status == "running":
            return self._reconcile_running_session(run, adapter=adapter, session=session)
        if session.status == "resuming":
            return self._reconcile_resuming_session(run, adapter=adapter, session=session)
        if session.status == "interrupted":
            return self._reconcile_interrupted_session(run, adapter=adapter, session=session)
        if session.status == "completed":
            return self._reconcile_completed_session(run, adapter=adapter, session=session)
        if session.status == "cancelled":
            return self._reconcile_cancelled_session(run, adapter=adapter, session=session)
        return self._reconcile_failed_session(run, adapter=adapter, session=session)

    def build_run_session_fields(
        self,
        session: RuntimeSessionRead,
    ) -> dict[str, object]:
        """Return run fields that mirror host-side runtime session metadata."""
        adapter = self.get_runtime_adapter(
            getattr(session, "runtime_target", None)
            or self._infer_runtime_target_from_session(session)
        )
        fields: dict[str, object] = {
            **adapter.build_session_identity_payload(session),
            "transport_kind": session.transport_kind,
            "transport_ref": session.transport_ref,
            "resume_attempt_count": session.resume_attempt_count,
        }
        interrupted_at = self.parse_terminal_timestamp(session.interrupted_at)
        if interrupted_at is not None:
            fields["interrupted_at"] = interrupted_at
        return fields

    def append_runtime_terminal_audit_event(
        self,
        *,
        run_id,
        adapter: BackendRuntimeAdapter,
    ) -> None:
        """Persist one runtime-specific execution trace when the runtime exposes it."""
        try:
            payload = adapter.get_terminal_audit_payload(str(run_id))
        except RuntimeAdapterError as exc:
            self.state_service.append_event(
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
        self.state_service.append_event(
            run_id=run_id,
            event_type=RunEventType.NOTE,
            payload=payload,
        )

    def finalize_completed_run(
        self,
        run,
        session: RuntimeSessionRead,
        *,
        skip_prepare_transition: bool = False,
    ):
        """Conclude one completed runtime session from the observed workspace delivery state."""
        if run.workspace_id is None:
            return self.state_service.fail_run(
                run,
                detail="Run is missing workspace metadata required for post-run finalization.",
            )

        try:
            prepare_message = "Inspecting runtime-managed SCM results in the prepared workspace."
            if skip_prepare_transition and run.status == RunStatus.COMMITTING.value:
                self.state_service.append_event(
                    run_id=run.id,
                    event_type=RunEventType.STATUS,
                    payload={
                        "status": RunStatus.COMMITTING.value,
                        "message": prepare_message,
                    },
                )
            else:
                run = self.state_service.transition_run(
                    run,
                    status_value=RunStatus.COMMITTING,
                    message=prepare_message,
                )
            return self.resolve_runtime_managed_workspace_outcome(
                run,
                summary_text=session.summary_text,
            )
        except WorkspaceProxyServiceError as exc:
            return self.state_service.fail_run(run, detail=exc.detail)
        except Exception as exc:  # noqa: BLE001
            return self.state_service.fail_run(run, detail=f"Run finalization failed: {exc}")

    def resolve_runtime_managed_workspace_outcome(
        self,
        run,
        *,
        summary_text: str | None,
    ):
        """Conclude one run strictly from runtime-managed workspace delivery state."""
        if run.workspace_id is None:
            return None

        workspace = self.workspace_proxy_service.get_workspace(run.workspace_id)
        adapter = self.get_runtime_adapter(run.runtime_target)
        runtime_label = adapter.label
        run = self.state_service.update_run(
            run,
            fields={
                "working_branch": workspace.working_branch,
                "workspace_path": workspace.workspace_path,
                "repo_path": workspace.repo_path,
                "summary": summary_text or run.summary,
            },
        )

        if workspace.status == "pull_request_created" and not workspace.has_changes:
            return self.state_service.complete_run(
                run,
                summary_text=summary_text,
                message="Runtime created the draft pull request from the working branch.",
                pr_url=workspace.pull_request_url,
            )

        if workspace.status == "pull_request_created":
            return self.state_service.fail_run(
                run,
                detail=(
                    f"{runtime_label} created a draft pull request but left additional "
                    "repository changes unfinalized in the workspace."
                ),
            )

        if workspace.status == "pushed":
            return self.state_service.fail_run(
                run,
                detail=(
                    f"{runtime_label} pushed the working branch but did not open the draft "
                    "pull request. The runtime must finish the PR step itself."
                ),
            )

        if workspace.status == "committed":
            return self.state_service.fail_run(
                run,
                detail=(
                    f"{runtime_label} created a local commit but did not push the working "
                    "branch or open the draft pull request."
                ),
            )

        if workspace.status == "prepared" and not workspace.has_changes:
            return self.state_service.complete_run(
                run,
                summary_text=summary_text,
                message=(
                    f"{runtime_label} session completed with no repository changes after "
                    "runtime cleanup."
                ),
            )

        return self.state_service.fail_run(
            run,
            detail=(
                f"{runtime_label} session completed but left repository changes unfinalized. "
                "The runtime must run `python3 .tap/finalize_run.py` before finishing the task."
            ),
        )

    @staticmethod
    def parse_terminal_timestamp(value: str | None) -> datetime | None:
        """Parse one host-side UTC timestamp emitted in terminal/session payloads."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _infer_runtime_target_from_session(session: RuntimeSessionRead) -> str:
        """Infer runtime target from a runtime-specific session payload shape."""
        if getattr(session, "claude_session_id", None) is not None:
            return RuntimeTarget.CLAUDE_CODE.value
        return RuntimeTarget.CODEX.value

    def _reconcile_running_session(self, run, *, adapter: BackendRuntimeAdapter, session: RuntimeSessionRead):
        fields = self.build_run_session_fields(session)
        auto_resume_advanced = (
            session.recovered_from_restart and session.resume_attempt_count > run.resume_attempt_count
        )
        if run.status == RunStatus.RESUMING.value:
            return self.state_service.update_run(
                run,
                fields={
                    **fields,
                    "status": RunStatus.RUNNING.value,
                    "error_message": None,
                    "finished_at": None,
                },
                events=[
                    RunEventSpec(
                        event_type=RunEventType.STATUS,
                        payload={
                            "status": RunStatus.RUNNING.value,
                            "message": f"{adapter.label} session resumed and is running again.",
                        },
                    ),
                    RunEventSpec(
                        event_type=RunEventType.NOTE,
                        payload=self._build_runtime_resume_completed_note_payload(
                            adapter=adapter,
                            session=session,
                            recovered_before_poll=False,
                        ),
                    ),
                ],
            )
        if auto_resume_advanced:
            return self.state_service.update_run(
                run,
                fields={
                    **fields,
                    "status": RunStatus.RUNNING.value,
                    "error_message": None,
                    "finished_at": None,
                },
                events=[
                    RunEventSpec(
                        event_type=RunEventType.NOTE,
                        payload=self._build_runtime_resume_completed_note_payload(
                            adapter=adapter,
                            session=session,
                            recovered_before_poll=True,
                        ),
                    )
                ],
            )
        if fields:
            return self.state_service.update_run(run, fields=fields)
        return run

    def _reconcile_resuming_session(self, run, *, adapter: BackendRuntimeAdapter, session: RuntimeSessionRead):
        previous_status = run.status
        updated = self.state_service.update_run(
            run,
            fields={
                **self.build_run_session_fields(session),
                "status": RunStatus.RESUMING.value,
                "error_message": None,
                "finished_at": None,
            },
        )
        if previous_status != RunStatus.RESUMING.value and session.recovered_from_restart:
            return self.state_service.update_run(
                updated,
                fields={},
                events=[
                    RunEventSpec(
                        event_type=RunEventType.STATUS,
                        payload={
                            "status": RunStatus.RESUMING.value,
                            "message": (
                                f"Host executor restarted and automatic {adapter.label} "
                                "recovery is in progress."
                            ),
                        },
                    ),
                    RunEventSpec(
                        event_type=RunEventType.NOTE,
                        payload=self._build_runtime_resume_started_note_payload(
                            adapter=adapter,
                            session=session,
                        ),
                    ),
                ],
            )
        return updated

    def _reconcile_interrupted_session(self, run, *, adapter: BackendRuntimeAdapter, session: RuntimeSessionRead):
        interrupted_at = self.parse_terminal_timestamp(session.interrupted_at)
        updated = self.state_service.update_run_if_status_in(
            run.id,
            statuses=self._RUNTIME_ACTIVE_STATUSES,
            fields={
                **self.build_run_session_fields(session),
                "status": RunStatus.INTERRUPTED.value,
                "error_message": session.error_message,
                "finished_at": interrupted_at or datetime.now(UTC),
                "interrupted_at": interrupted_at or datetime.now(UTC),
            },
            events=[
                RunEventSpec(
                    event_type=RunEventType.STATUS,
                    payload={
                        "status": RunStatus.INTERRUPTED.value,
                        "message": session.error_message or f"{adapter.label} session was interrupted.",
                    },
                ),
                RunEventSpec(
                    event_type=RunEventType.NOTE,
                    payload=self._build_runtime_interrupted_note_payload(
                        adapter=adapter,
                        session=session,
                    ),
                ),
                *(
                    [
                        RunEventSpec(
                            event_type=RunEventType.NOTE,
                            payload=self._build_runtime_resume_available_note_payload(
                                adapter=adapter,
                                session=session,
                            ),
                        )
                    ]
                    if session.resumable
                    else []
                ),
            ],
        )
        if updated is None:
            refreshed = self.run_repository.get_by_id(run.id)
            return refreshed or run
        self.append_runtime_terminal_audit_event(run_id=updated.id, adapter=adapter)
        return updated

    def _reconcile_completed_session(self, run, *, adapter: BackendRuntimeAdapter, session: RuntimeSessionRead):
        if run.status == RunStatus.COMMITTING.value:
            claimed = self.state_service.update_run(
                run,
                fields={
                    **self.build_run_session_fields(session),
                    "error_message": None,
                    "finished_at": None,
                },
            )
        else:
            claimed = self.state_service.update_run_if_status_in(
                run.id,
                statuses=self._RUNTIME_ACTIVE_STATUSES,
                fields={
                    **self.build_run_session_fields(session),
                    "status": RunStatus.COMMITTING.value,
                    "error_message": None,
                    "finished_at": None,
                },
            )
            if claimed is None:
                refreshed = self.run_repository.get_by_id(run.id)
                return refreshed or run

        self.append_runtime_terminal_audit_event(run_id=claimed.id, adapter=adapter)
        return self.finalize_completed_run(
            claimed,
            session,
            skip_prepare_transition=True,
        )

    def _reconcile_cancelled_session(self, run, *, adapter: BackendRuntimeAdapter, session: RuntimeSessionRead):
        updated = self.state_service.update_run_if_status_in(
            run.id,
            statuses=self._RUNTIME_ACTIVE_STATUSES,
            fields={
                **self.build_run_session_fields(session),
                "status": RunStatus.CANCELLED.value,
                "error_message": None,
                "finished_at": self.parse_terminal_timestamp(session.finished_at)
                or datetime.now(UTC),
            },
            events=[
                RunEventSpec(
                    event_type=RunEventType.STATUS,
                    payload={
                        "status": RunStatus.CANCELLED.value,
                        "message": f"{adapter.label} session was cancelled.",
                    },
                )
            ],
        )
        if updated is None:
            refreshed = self.run_repository.get_by_id(run.id)
            return refreshed or run
        self.append_runtime_terminal_audit_event(run_id=updated.id, adapter=adapter)
        return updated

    def _reconcile_failed_session(self, run, *, adapter: BackendRuntimeAdapter, session: RuntimeSessionRead):
        updated = self.state_service.update_run_if_status_in(
            run.id,
            statuses=self._RUNTIME_ACTIVE_STATUSES,
            fields={
                **self.build_run_session_fields(session),
                "status": RunStatus.FAILED.value,
                "error_message": session.error_message or f"{adapter.label} session failed.",
                "finished_at": self.parse_terminal_timestamp(session.finished_at)
                or datetime.now(UTC),
            },
            events=[
                RunEventSpec(
                    event_type=RunEventType.STATUS,
                    payload={
                        "status": RunStatus.FAILED.value,
                        "message": session.error_message or f"{adapter.label} session failed.",
                    },
                ),
                RunEventSpec(
                    event_type=RunEventType.ERROR,
                    payload={"detail": session.error_message or f"{adapter.label} session failed."},
                ),
            ],
        )
        if updated is None:
            refreshed = self.run_repository.get_by_id(run.id)
            return refreshed or run
        self.append_runtime_terminal_audit_event(run_id=updated.id, adapter=adapter)
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
