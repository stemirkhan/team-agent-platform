"""Host-side Claude Code session management."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from host_executor_app.schemas.claude import (
    ClaudeSessionEventsResponse,
    ClaudeSessionRead,
    ClaudeSessionStart,
    ClaudeTerminalChunk,
)
from host_executor_app.services.runtime_session_engine import (
    BaseRuntimeSessionService,
    RuntimeLaunchConfig,
    RuntimeSessionServiceError,
    RuntimeSessionState,
    _utc_now,
)


@dataclass(slots=True)
class ClaudeSessionServiceError(RuntimeSessionServiceError):
    """Normalized error raised for Claude session failures."""


@dataclass(slots=True)
class _ClaudeSessionState(RuntimeSessionState):
    """Internal mutable state for one Claude subprocess."""

    claude_session_id: str | None = None


class ClaudeSessionService(BaseRuntimeSessionService):
    """Manage in-memory host-side Claude sessions keyed by run id."""

    runtime_label = "Claude"
    cli_label = "Claude Code CLI"
    sessions_dir_name = "claude-sessions"
    thread_name_prefix = "claude"
    tmux_session_prefix = "tap-claude-run"
    error_cls = ClaudeSessionServiceError
    read_model = ClaudeSessionRead
    chunk_model = ClaudeTerminalChunk
    events_response_model = ClaudeSessionEventsResponse

    _SUMMARY_MAX_LENGTH = 320
    _SUMMARY_SECTION_MARKERS = (
        "Main files changed:",
        "Validation:",
        "Most logical next step:",
        "Notes:",
        "## Notes",
    )
    _RESUME_PROMPT = (
        "Host executor restarted. Continue the previous task from the current repository state. "
        "First inspect git status and pending work. "
        "Do not restart the task from scratch unless required."
    )

    def _validate_start_workspace(self, *, repo_path: Path, payload: ClaudeSessionStart) -> None:
        """Validate the prepared Claude workspace before launch."""
        task_path = repo_path / "TASK.md"
        if not task_path.exists():
            raise ClaudeSessionServiceError(409, "Workspace is missing `TASK.md`.")

    def _prepare_start_launch(
        self,
        *,
        repo_path: Path,
        payload: ClaudeSessionStart,
    ) -> RuntimeLaunchConfig:
        """Build the Claude launch config for one fresh run."""
        session_id = self._session_id_for_run(payload.run_id)
        return RuntimeLaunchConfig(
            command=self._build_command(payload=payload, session_id=session_id),
        )

    def _prepare_resume_launch(
        self,
        state: _ClaudeSessionState,
        repo_path: Path,
        *,
        auto_resume: bool,
    ) -> RuntimeLaunchConfig:
        """Build the Claude launch config used to resume one interrupted run."""
        del repo_path
        del auto_resume
        return RuntimeLaunchConfig(
            command=self._build_resume_command(state.claude_session_id or ""),
        )

    def _build_started_state(
        self,
        *,
        payload: ClaudeSessionStart,
        repo_path: Path,
        storage_dir: Path,
        launch: RuntimeLaunchConfig,
        process,
        master_fd: int | None,
        pid: int | None,
        transport_kind: str,
        transport_ref: str | None,
    ) -> _ClaudeSessionState:
        """Construct the in-memory state for one started Claude run."""
        return _ClaudeSessionState(
            run_id=payload.run_id,
            workspace_id=payload.workspace_id,
            repo_path=str(repo_path),
            command=launch.command,
            storage_dir=str(storage_dir),
            process=process,
            master_fd=master_fd,
            started_at=_utc_now(),
            pid=pid,
            claude_session_id=self._session_id_for_run(payload.run_id),
            transport_kind=transport_kind,
            transport_ref=transport_ref,
        )

    def _build_state_from_session(
        self,
        *,
        session: ClaudeSessionRead,
        storage_dir: Path,
        chunks: list[ClaudeTerminalChunk],
    ) -> _ClaudeSessionState:
        """Restore Claude runtime state from persisted public session data."""
        return _ClaudeSessionState(
            run_id=session.run_id,
            workspace_id=session.workspace_id,
            repo_path=session.repo_path,
            command=session.command,
            storage_dir=str(storage_dir),
            started_at=session.started_at,
            status=session.status,
            pid=session.pid,
            exit_code=session.exit_code,
            error_message=session.error_message,
            summary_text=session.summary_text,
            claude_session_id=session.claude_session_id or session.runtime_session_id,
            transport_kind=session.transport_kind,
            transport_ref=session.transport_ref,
            resume_attempt_count=session.resume_attempt_count,
            interrupted_at=session.interrupted_at,
            resumable=session.resumable,
            recovered_from_restart=session.recovered_from_restart,
            output_bytes_read=session.output_bytes_read,
            finished_at=session.finished_at,
            chunks=chunks,
        )

    def _get_runtime_session_id(self, state: _ClaudeSessionState) -> str | None:
        """Return the persisted Claude session id when available."""
        return state.claude_session_id

    @classmethod
    def _build_command(cls, *, payload: ClaudeSessionStart, session_id: str) -> list[str]:
        """Return the Claude CLI command for one run."""
        command = [
            "claude",
            "-p",
            "--verbose",
            "--output-format",
            "stream-json",
            "--permission-mode",
            payload.permission_mode,
            "--session-id",
            session_id,
        ]
        if payload.model:
            command.extend(["--model", payload.model])
        if payload.effort:
            command.extend(["--effort", payload.effort])
        return command

    @classmethod
    def _build_resume_command(cls, claude_session_id: str) -> list[str]:
        """Return the Claude CLI command used to resume one persisted session."""
        return [
            "claude",
            "-p",
            "--verbose",
            "--output-format",
            "stream-json",
            "--permission-mode",
            "bypassPermissions",
            "--resume",
            claude_session_id,
            cls._RESUME_PROMPT,
        ]

    @staticmethod
    def _session_id_for_run(run_id: str) -> str:
        """Return a deterministic Claude session UUID for one run id."""
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"tap-claude/{run_id}"))

    @classmethod
    def _derive_summary(cls, chunks: list[ClaudeTerminalChunk]) -> str | None:
        """Return the latest assistant/result summary from Claude stream-json output."""
        last_assistant_message: str | None = None
        last_result_message: str | None = None

        for payload in cls._iter_json_objects(chunks):
            payload_type = payload.get("type")
            if payload_type == "assistant":
                message = payload.get("message")
                text = cls._extract_assistant_text(message)
                if text:
                    last_assistant_message = cls._normalize_summary_candidate(text)
                continue

            if payload_type != "result":
                continue

            result = payload.get("result")
            if isinstance(result, str) and result.strip():
                normalized = cls._normalize_summary_candidate(result)
                if normalized:
                    last_result_message = normalized

        return last_result_message or last_assistant_message

    @staticmethod
    def _extract_assistant_text(message: object) -> str | None:
        """Return joined text content from one Claude assistant message payload."""
        if not isinstance(message, dict):
            return None
        content = message.get("content")
        if not isinstance(content, list):
            return None
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "text":
                continue
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
        if not parts:
            return None
        return "\n".join(parts)

    @classmethod
    def _normalize_summary_candidate(cls, value: str) -> str | None:
        """Return a concise run summary suitable for UI and PR body display."""
        normalized = value.strip()
        if not normalized:
            return None

        normalized = re.sub(r"\x1b\[[0-9;]*m", "", normalized)
        normalized = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", normalized)
        normalized = re.sub(r"`([^`]+)`", r"\1", normalized)

        paragraph_break = re.search(r"\n\s*\n", normalized)
        if paragraph_break:
            normalized = normalized[: paragraph_break.start()]

        for marker in cls._SUMMARY_SECTION_MARKERS:
            marker_index = normalized.find(marker)
            if marker_index > 0:
                normalized = normalized[:marker_index]
                break

        normalized = re.sub(r"\s+", " ", normalized).strip()
        if not normalized or cls._looks_like_code_summary(normalized):
            return None

        if len(normalized) <= cls._SUMMARY_MAX_LENGTH:
            return normalized

        sentence_boundary = max(
            normalized.rfind(". ", 0, cls._SUMMARY_MAX_LENGTH),
            normalized.rfind("! ", 0, cls._SUMMARY_MAX_LENGTH),
            normalized.rfind("? ", 0, cls._SUMMARY_MAX_LENGTH),
        )
        if sentence_boundary >= 120:
            return normalized[: sentence_boundary + 1].strip()

        clipped = normalized[: cls._SUMMARY_MAX_LENGTH - 3].rstrip(" ,;:-")
        return f"{clipped}..."

    @staticmethod
    def _looks_like_code_summary(value: str) -> bool:
        """Return whether the candidate looks like code instead of prose."""
        lowered = value.lower()
        code_markers = (
            "classname=",
            "<div",
            "</div",
            "function ",
            "const ",
            "return ",
            "=>",
            "import ",
            "export ",
        )
        return any(marker in lowered for marker in code_markers)

    @staticmethod
    def _iter_json_objects(chunks: list[ClaudeTerminalChunk]):
        """Yield parsed JSON objects reconstructed from chunked stream-json output."""
        buffer = ""

        for chunk in chunks:
            combined = f"{buffer}{chunk.text}".replace("\r\n", "\n")
            lines = combined.split("\n")
            buffer = lines.pop() or ""

            for line in lines:
                stripped = line.strip()
                if not stripped.startswith("{"):
                    continue
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    yield payload

        if not buffer.strip().startswith("{"):
            return

        try:
            payload = json.loads(buffer.strip())
        except json.JSONDecodeError:
            return
        if isinstance(payload, dict):
            yield payload

    @classmethod
    def _derive_error_message(cls, chunks: list[ClaudeTerminalChunk], *, exit_code: int) -> str:
        """Extract a readable failure message from Claude terminal output."""
        payloads = list(cls._iter_json_objects(chunks))
        for payload in reversed(payloads):
            if payload.get("type") != "result":
                continue
            result = payload.get("result")
            if isinstance(result, str) and result.strip():
                return result.strip()
            errors = payload.get("errors")
            if isinstance(errors, list) and errors:
                first = errors[0]
                if isinstance(first, str) and first.strip():
                    return first.strip()
                if isinstance(first, dict):
                    detail = first.get("message")
                    if isinstance(detail, str) and detail.strip():
                        return detail.strip()
            subtype = payload.get("subtype")
            if isinstance(subtype, str) and subtype.strip():
                return f"Claude session ended with {subtype}."

        lines: list[str] = []
        for chunk in chunks:
            lines.extend(chunk.text.splitlines())
        for line in reversed(lines):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("Error:"):
                return stripped.removeprefix("Error:").strip()

        return f"Claude Code CLI exited with code {exit_code}."

    @classmethod
    def _derive_usage_metrics(
        cls,
        chunks: list[ClaudeTerminalChunk],
    ) -> tuple[int | None, int | None]:
        """Return the latest token usage reported by Claude stream-json events."""
        input_tokens: int | None = None
        output_tokens: int | None = None

        for payload in cls._iter_json_objects(chunks):
            payload_type = payload.get("type")
            usage: object | None = None
            if payload_type == "assistant":
                message = payload.get("message")
                if isinstance(message, dict):
                    usage = message.get("usage")
            elif payload_type == "result":
                usage = payload.get("usage")
            if not isinstance(usage, dict):
                continue

            raw_input = usage.get("input_tokens")
            raw_output = usage.get("output_tokens")
            next_input = raw_input if isinstance(raw_input, int) else None
            next_output = raw_output if isinstance(raw_output, int) else None
            if next_input is not None:
                input_tokens = next_input
            if next_output is not None:
                output_tokens = next_output

        return input_tokens, output_tokens

    @staticmethod
    def _to_read(state: _ClaudeSessionState) -> ClaudeSessionRead:
        """Convert internal state into a public API payload."""
        input_tokens, output_tokens = ClaudeSessionService._derive_usage_metrics(state.chunks)
        return ClaudeSessionRead(
            run_id=state.run_id,
            workspace_id=state.workspace_id,
            repo_path=state.repo_path,
            command=state.command,
            status=state.status,  # type: ignore[arg-type]
            pid=state.pid,
            exit_code=state.exit_code,
            error_message=state.error_message,
            summary_text=state.summary_text,
            runtime_session_id=state.claude_session_id,
            claude_session_id=state.claude_session_id,
            transport_kind=state.transport_kind,  # type: ignore[arg-type]
            transport_ref=state.transport_ref,
            resume_attempt_count=state.resume_attempt_count,
            interrupted_at=state.interrupted_at,
            resumable=state.resumable,
            recovered_from_restart=state.recovered_from_restart,
            output_bytes_read=state.output_bytes_read,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            started_at=state.started_at,
            finished_at=state.finished_at,
            last_output_offset=len(state.chunks),
        )
