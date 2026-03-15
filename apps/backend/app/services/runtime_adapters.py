"""Runtime-specific adapters used by backend run orchestration."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from typing import Protocol
from zipfile import ZipFile

from app.models.export_job import ExportEntityType, RuntimeTarget
from app.schemas.claude import ClaudeSessionEventsResponse, ClaudeSessionRead, ClaudeSessionStart
from app.schemas.codex import CodexSessionEventsResponse, CodexSessionRead, CodexSessionStart
from app.schemas.export import CodexExportOptions
from app.schemas.terminal import TerminalChunk, TerminalSessionEventsResponse, TerminalSessionRead
from app.schemas.workspace import WorkspaceFileWrite
from app.services.claude_proxy_service import ClaudeProxyService, ClaudeProxyServiceError
from app.services.codex_proxy_service import CodexProxyService, CodexProxyServiceError
from app.services.export_service import ExportService

RuntimeSessionRead = CodexSessionRead | ClaudeSessionRead
RuntimeSessionEvents = CodexSessionEventsResponse | ClaudeSessionEventsResponse


@dataclass(slots=True)
class RuntimeAdapterError(Exception):
    """Normalized runtime adapter error."""

    status_code: int
    detail: str


class BackendRuntimeAdapter(Protocol):
    """Small runtime boundary used by backend orchestration."""

    runtime_target: str
    label: str
    bundle_label: str
    summary_label: str
    event_prefix: str
    session_id_field_name: str

    def start_session(
        self,
        *,
        run_id: str,
        workspace_id: str,
        task_markdown: str,
        codex_options: CodexExportOptions | None,
    ) -> RuntimeSessionRead: ...

    def get_session(self, run_id: str) -> RuntimeSessionRead: ...

    def get_events(self, run_id: str, *, offset: int) -> RuntimeSessionEvents: ...

    def cancel_session(self, run_id: str) -> RuntimeSessionRead: ...

    def resume_session(self, run_id: str) -> RuntimeSessionRead: ...

    def build_materialization_audit_payload(
        self,
        *,
        files: list[WorkspaceFileWrite],
    ) -> dict[str, object] | None: ...

    def build_workspace_files(
        self,
        *,
        export_service: ExportService,
        team_slug: str,
        task_markdown: str,
        codex_options: CodexExportOptions | None,
    ) -> list[WorkspaceFileWrite]: ...

    def get_terminal_audit_payload(self, run_id: str) -> dict[str, object] | None: ...

    def normalize_terminal_session(self, session: RuntimeSessionRead) -> TerminalSessionRead: ...

    def normalize_terminal_events(
        self,
        session_events: RuntimeSessionEvents,
    ) -> TerminalSessionEventsResponse: ...

    def build_session_identity_payload(self, session: RuntimeSessionRead) -> dict[str, object]: ...

    def build_note_session_payload(self, session: RuntimeSessionRead) -> dict[str, object]: ...


class RuntimeAdapterRegistry:
    """Registry for runtime adapters keyed by runtime target."""

    def __init__(self, adapters: list[BackendRuntimeAdapter]) -> None:
        self._adapters = {adapter.runtime_target: adapter for adapter in adapters}

    def get(self, runtime_target: str) -> BackendRuntimeAdapter | None:
        """Return one adapter by runtime target when available."""
        return self._adapters.get(runtime_target)


class _RuntimeAdapterBase:
    """Shared helper methods for backend runtime adapters."""

    runtime_target: str
    label: str
    bundle_label: str
    summary_label: str
    event_prefix: str
    session_id_field_name: str

    def build_session_identity_payload(self, session: RuntimeSessionRead) -> dict[str, object]:
        """Return generic plus runtime-specific session identity fields."""
        runtime_session_id = self._runtime_session_id(session)
        payload = {
            "runtime_session_id": runtime_session_id,
            "codex_session_id": getattr(session, "codex_session_id", None),
            "claude_session_id": getattr(session, "claude_session_id", None),
        }
        if self.session_id_field_name == "codex_session_id":
            payload["codex_session_id"] = runtime_session_id
        if self.session_id_field_name == "claude_session_id":
            payload["claude_session_id"] = runtime_session_id
        return payload

    def get_terminal_audit_payload(self, run_id: str) -> dict[str, object] | None:
        """Build one runtime-specific execution-trace payload from terminal output."""
        session_events = self.get_events(run_id, offset=0)
        return self._build_terminal_audit_payload(session_events)

    def normalize_terminal_session(self, session: RuntimeSessionRead) -> TerminalSessionRead:
        """Convert runtime-specific session metadata into the shared terminal contract."""
        return TerminalSessionRead(
            runtime_target=self.runtime_target,  # type: ignore[arg-type]
            run_id=session.run_id,
            workspace_id=session.workspace_id,
            repo_path=session.repo_path,
            command=list(session.command),
            status=session.status,  # type: ignore[arg-type]
            pid=session.pid,
            exit_code=session.exit_code,
            error_message=session.error_message,
            summary_text=session.summary_text,
            runtime_session_id=getattr(session, "runtime_session_id", None)
            or getattr(session, "codex_session_id", None)
            or getattr(session, "claude_session_id", None),
            codex_session_id=getattr(session, "codex_session_id", None),
            claude_session_id=getattr(session, "claude_session_id", None),
            transport_kind=session.transport_kind,  # type: ignore[arg-type]
            transport_ref=session.transport_ref,
            resume_attempt_count=session.resume_attempt_count,
            interrupted_at=session.interrupted_at,
            resumable=session.resumable,
            recovered_from_restart=session.recovered_from_restart,
            input_tokens=session.input_tokens,
            output_tokens=session.output_tokens,
            started_at=session.started_at,
            finished_at=session.finished_at,
            last_output_offset=session.last_output_offset,
        )

    def normalize_terminal_events(
        self,
        session_events: RuntimeSessionEvents,
    ) -> TerminalSessionEventsResponse:
        """Convert runtime-specific terminal payloads into the shared API contract."""
        return TerminalSessionEventsResponse(
            session=self.normalize_terminal_session(session_events.session),
            items=[
                TerminalChunk(
                    offset=item.offset,
                    text=item.text,
                    created_at=item.created_at,
                )
                for item in session_events.items
            ],
            next_offset=session_events.next_offset,
        )

    def build_note_session_payload(self, session: RuntimeSessionRead) -> dict[str, object]:
        """Return the runtime-specific session id fields used in run event payloads."""
        runtime_session_id = self._runtime_session_id(session)
        if runtime_session_id is None:
            return {}
        return {self.session_id_field_name: runtime_session_id}

    def build_workspace_files(
        self,
        *,
        export_service: ExportService,
        team_slug: str,
        task_markdown: str,
        codex_options: CodexExportOptions | None,
    ) -> list[WorkspaceFileWrite]:
        """Build the runtime bundle files plus TASK.md for one prepared workspace."""
        _, bundle_bytes, _ = export_service.build_download_artifact(
            entity_type=ExportEntityType.TEAM,
            slug=team_slug,
            runtime_target=self.runtime_target,
            codex_options=(
                codex_options if self.runtime_target == RuntimeTarget.CODEX.value else None
            ),
        )
        files = self._extract_text_files_from_zip(bundle_bytes)
        files["TASK.md"] = task_markdown
        return [
            WorkspaceFileWrite(path=path, content=content)
            for path, content in sorted(files.items())
        ]

    def _runtime_session_id(self, session: RuntimeSessionRead) -> str | None:
        """Return the runtime-specific durable session id."""
        return getattr(session, self.session_id_field_name, None)

    @staticmethod
    def _iter_terminal_lines(session_events: RuntimeSessionEvents) -> list[str]:
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

    def _build_terminal_audit_payload(
        self,
        session_events: RuntimeSessionEvents,
    ) -> dict[str, object] | None:
        """Return one runtime-specific execution-trace payload when supported."""
        return None

    @staticmethod
    def _extract_text_files_from_zip(content: bytes) -> dict[str, str]:
        """Extract UTF-8 text files from a generated runtime bundle zip."""
        files: dict[str, str] = {}
        with ZipFile(BytesIO(content)) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                normalized = PurePosixPath(member.filename)
                if normalized.is_absolute() or any(
                    part in {"", ".", ".."} for part in normalized.parts
                ):
                    raise RuntimeAdapterError(
                        502,
                        "Generated export bundle contains an invalid file path.",
                    )
                files[str(normalized)] = archive.read(member).decode("utf-8")
        return files


class CodexRuntimeAdapter(_RuntimeAdapterBase):
    """Runtime adapter for Codex session orchestration."""

    runtime_target = RuntimeTarget.CODEX.value
    label = "Codex"
    bundle_label = "`.codex` bundle"
    summary_label = "codex"
    event_prefix = "codex"
    session_id_field_name = "codex_session_id"

    def __init__(self, proxy_service: CodexProxyService) -> None:
        self.proxy_service = proxy_service

    def start_session(
        self,
        *,
        run_id: str,
        workspace_id: str,
        task_markdown: str,
        codex_options: CodexExportOptions | None,
    ) -> CodexSessionRead:
        """Start one host-side Codex session."""
        try:
            return self.proxy_service.start_session(
                payload=CodexSessionStart(
                    run_id=run_id,
                    workspace_id=workspace_id,
                    prompt_text=task_markdown,
                    model=codex_options.model if codex_options is not None else None,
                    model_reasoning_effort=(
                        codex_options.model_reasoning_effort
                        if codex_options is not None
                        else None
                    ),
                    sandbox_mode=(
                        codex_options.sandbox_mode
                        if codex_options is not None
                        else "workspace-write"
                    ),
                )
            )
        except CodexProxyServiceError as exc:
            raise RuntimeAdapterError(exc.status_code, exc.detail) from exc

    def get_session(self, run_id: str) -> CodexSessionRead:
        """Return one Codex session."""
        try:
            return self.proxy_service.get_session(run_id)
        except CodexProxyServiceError as exc:
            raise RuntimeAdapterError(exc.status_code, exc.detail) from exc

    def get_events(self, run_id: str, *, offset: int) -> CodexSessionEventsResponse:
        """Return incremental Codex terminal output."""
        try:
            return self.proxy_service.get_events(run_id, offset=offset)
        except CodexProxyServiceError as exc:
            raise RuntimeAdapterError(exc.status_code, exc.detail) from exc

    def cancel_session(self, run_id: str) -> CodexSessionRead:
        """Cancel one Codex session."""
        try:
            return self.proxy_service.cancel_session(run_id)
        except CodexProxyServiceError as exc:
            raise RuntimeAdapterError(exc.status_code, exc.detail) from exc

    def resume_session(self, run_id: str) -> CodexSessionRead:
        """Resume one Codex session."""
        try:
            return self.proxy_service.resume_session(run_id)
        except CodexProxyServiceError as exc:
            raise RuntimeAdapterError(exc.status_code, exc.detail) from exc

    def build_materialization_audit_payload(
        self,
        *,
        files: list[WorkspaceFileWrite],
    ) -> dict[str, object]:
        """Build the Codex bundle audit payload."""
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

        return {
            "kind": "codex_bundle",
            "message": message,
            "multi_agent_enabled": multi_agent_enabled,
            "configured_agents": configured_agents,
            "config_toml": config_toml,
            "agent_configs": agent_configs,
            "task_markdown": task_markdown,
        }

    def _build_terminal_audit_payload(
        self,
        session_events: CodexSessionEventsResponse,
    ) -> dict[str, object]:
        """Summarize structured Codex collaboration events."""
        spawned_agents_by_thread: dict[str, dict[str, str | None]] = {}
        item_type_counts: dict[str, int] = {}

        for line in self._iter_terminal_lines(session_events):
            if "WARN codex_core::file_watcher: failed to unwatch" in line:
                continue
            if not line.strip():
                continue

            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue

            item = payload.get("item")
            if not isinstance(item, dict):
                continue

            item_type = item.get("type")
            if not isinstance(item_type, str):
                continue
            item_type_counts[item_type] = item_type_counts.get(item_type, 0) + 1

            if item_type != "collab_tool_call":
                continue

            tool = item.get("tool")
            receiver_thread_ids = self._coerce_receiver_thread_ids(item.get("receiver_thread_ids"))
            if not receiver_thread_ids:
                continue

            if tool == "spawn_agent":
                self._merge_spawned_agent_states(
                    spawned_agents_by_thread=spawned_agents_by_thread,
                    receiver_thread_ids=receiver_thread_ids,
                    role=self._read_structured_role(item),
                    agents_states=item.get("agents_states"),
                )
                continue

            if tool in {"wait", "close_agent"}:
                self._merge_spawned_agent_states(
                    spawned_agents_by_thread=spawned_agents_by_thread,
                    receiver_thread_ids=receiver_thread_ids,
                    role=None,
                    agents_states=item.get("agents_states"),
                )

        spawned_agents = list(spawned_agents_by_thread.values())
        if spawned_agents:
            signal_level = "confirmed"
            message = (
                f"Observed {len(spawned_agents)} spawned agent(s) via collaboration tool calls; "
                "this is confirmed sub-agent execution."
            )
        else:
            signal_level = "none"
            message = (
                "No confirmed sub-agent spawn signals were captured in the Codex terminal output."
            )

        return {
            "kind": "codex_execution_trace",
            "message": message,
            "multi_agent_signal_level": signal_level,
            "chunk_count": len(session_events.items),
            "spawned_agents": spawned_agents[:10],
            "item_type_counts": item_type_counts,
        }

    @staticmethod
    def _extract_configured_agents(config_toml: str | None) -> list[str]:
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
    def _read_structured_role(value: object) -> str | None:
        """Return one explicit role slug when it is present in structured tool payloads."""
        if not isinstance(value, dict):
            return None
        for key in ("role", "role_name", "agent_role"):
            role = value.get(key)
            if isinstance(role, str) and role.strip():
                return role.strip()
        return None

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
            if normalized:
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
                },
            )
            if role and not agent.get("role"):
                agent["role"] = role

            state_payload = agent_state_map.get(thread_id)
            if not isinstance(state_payload, dict):
                continue
            structured_role = cls._read_structured_role(state_payload)
            if structured_role and not agent.get("role"):
                agent["role"] = structured_role
            status = state_payload.get("status")
            if isinstance(status, str) and status.strip():
                agent["status"] = status.strip()


class ClaudeRuntimeAdapter(_RuntimeAdapterBase):
    """Runtime adapter for Claude Code session orchestration."""

    runtime_target = RuntimeTarget.CLAUDE_CODE.value
    label = "Claude Code"
    bundle_label = "`.claude` bundle"
    summary_label = "Claude Code"
    event_prefix = "claude"
    session_id_field_name = "claude_session_id"

    def __init__(self, proxy_service: ClaudeProxyService) -> None:
        self.proxy_service = proxy_service

    def start_session(
        self,
        *,
        run_id: str,
        workspace_id: str,
        task_markdown: str,
        codex_options: CodexExportOptions | None,
    ) -> ClaudeSessionRead:
        """Start one host-side Claude Code session."""
        try:
            return self.proxy_service.start_session(
                payload=ClaudeSessionStart(
                    run_id=run_id,
                    workspace_id=workspace_id,
                    prompt_text=task_markdown,
                )
            )
        except ClaudeProxyServiceError as exc:
            raise RuntimeAdapterError(exc.status_code, exc.detail) from exc

    def get_session(self, run_id: str) -> ClaudeSessionRead:
        """Return one Claude Code session."""
        try:
            return self.proxy_service.get_session(run_id)
        except ClaudeProxyServiceError as exc:
            raise RuntimeAdapterError(exc.status_code, exc.detail) from exc

    def get_events(self, run_id: str, *, offset: int) -> ClaudeSessionEventsResponse:
        """Return incremental Claude Code terminal output."""
        try:
            return self.proxy_service.get_events(run_id, offset=offset)
        except ClaudeProxyServiceError as exc:
            raise RuntimeAdapterError(exc.status_code, exc.detail) from exc

    def cancel_session(self, run_id: str) -> ClaudeSessionRead:
        """Cancel one Claude Code session."""
        try:
            return self.proxy_service.cancel_session(run_id)
        except ClaudeProxyServiceError as exc:
            raise RuntimeAdapterError(exc.status_code, exc.detail) from exc

    def resume_session(self, run_id: str) -> ClaudeSessionRead:
        """Resume one Claude Code session."""
        try:
            return self.proxy_service.resume_session(run_id)
        except ClaudeProxyServiceError as exc:
            raise RuntimeAdapterError(exc.status_code, exc.detail) from exc

    def build_materialization_audit_payload(
        self,
        *,
        files: list[WorkspaceFileWrite],
    ) -> dict[str, object]:
        """Build the Claude Code bundle audit payload."""
        file_map = {item.path: item.content for item in files}
        agent_files = [
            {
                "name": path.rsplit("/", maxsplit=1)[-1].removesuffix(".md"),
                "path": path,
                "content": content,
            }
            for path, content in sorted(file_map.items())
            if path.startswith(".claude/agents/") and path.endswith(".md")
        ]
        return {
            "kind": "claude_bundle",
            "message": (
                f"Materialized Claude Code subagent bundle with {len(agent_files)} "
                "configured role(s)."
            ),
            "agent_files": agent_files,
            "task_markdown": file_map.get("TASK.md"),
        }

    def _build_terminal_audit_payload(
        self,
        session_events: ClaudeSessionEventsResponse,
    ) -> dict[str, object]:
        """Summarize structured Claude subagent launch signals from stream-json output."""
        item_type_counts: dict[str, int] = {}
        subagent_tasks_by_tool_use_id: dict[str, dict[str, str | None]] = {}
        subagent_tasks_by_task_id: dict[str, dict[str, str | None]] = {}

        for line in self._iter_terminal_lines(session_events):
            if not line.strip():
                continue

            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue

            event_type = payload.get("type")
            if isinstance(event_type, str):
                item_type_counts[event_type] = item_type_counts.get(event_type, 0) + 1

            if payload.get("type") == "assistant":
                message = payload.get("message")
                if not isinstance(message, dict):
                    continue
                content = message.get("content")
                if not isinstance(content, list):
                    continue
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") != "tool_use" or item.get("name") != "Agent":
                        continue
                    tool_use_id = item.get("id")
                    if not isinstance(tool_use_id, str) or not tool_use_id.strip():
                        continue
                    tool_input = item.get("input")
                    if not isinstance(tool_input, dict):
                        tool_input = {}
                    agent = subagent_tasks_by_tool_use_id.setdefault(
                        tool_use_id,
                        {
                            "tool_use_id": tool_use_id,
                            "task_id": None,
                            "role": _read_claude_subagent_role(tool_input),
                            "description": _read_claude_subagent_description(tool_input),
                            "status": "launched",
                        },
                    )
                    role = _read_claude_subagent_role(tool_input)
                    if role and not agent.get("role"):
                        agent["role"] = role
                    description = _read_claude_subagent_description(tool_input)
                    if description and not agent.get("description"):
                        agent["description"] = description
                continue

            if payload.get("type") != "system":
                continue

            subtype = payload.get("subtype")
            if subtype == "task_started":
                tool_use_id = payload.get("tool_use_id")
                task_id = payload.get("task_id")
                if not isinstance(tool_use_id, str) or tool_use_id not in subagent_tasks_by_tool_use_id:
                    continue
                agent = subagent_tasks_by_tool_use_id[tool_use_id]
                if isinstance(task_id, str) and task_id.strip():
                    agent["task_id"] = task_id
                    subagent_tasks_by_task_id[task_id] = agent
                description = payload.get("description")
                if isinstance(description, str) and description.strip() and not agent.get(
                    "description"
                ):
                    agent["description"] = description.strip()
                agent["status"] = "running"
                continue

            if subtype == "task_progress":
                task_id = payload.get("task_id")
                if not isinstance(task_id, str) or task_id not in subagent_tasks_by_task_id:
                    continue
                agent = subagent_tasks_by_task_id[task_id]
                agent["status"] = "running"

        spawned_agents = list(subagent_tasks_by_tool_use_id.values())
        if spawned_agents:
            signal_level = "confirmed"
            message = (
                f"Observed {len(spawned_agents)} Claude subagent launch signal(s) via "
                "the Agent tool."
            )
        else:
            signal_level = "none"
            message = "No confirmed Claude subagent launch signals were captured in the terminal output."

        return {
            "kind": "claude_execution_trace",
            "message": message,
            "multi_agent_signal_level": signal_level,
            "chunk_count": len(session_events.items),
            "spawned_agents": spawned_agents[:10],
            "item_type_counts": item_type_counts,
        }


def _read_claude_subagent_role(value: dict[str, object]) -> str | None:
    """Return the Claude subagent role when it is present."""
    role = value.get("subagent_type")
    if isinstance(role, str) and role.strip():
        return role.strip()
    return None


def _read_claude_subagent_description(value: dict[str, object]) -> str | None:
    """Return the Claude subagent description when it is present."""
    description = value.get("description")
    if isinstance(description, str) and description.strip():
        return description.strip()
    return None
