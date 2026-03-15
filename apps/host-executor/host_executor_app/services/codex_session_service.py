"""Host-side Codex PTY session management."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from host_executor_app.schemas.codex import (
    CodexSessionEventsResponse,
    CodexSessionRead,
    CodexSessionStart,
    CodexTerminalChunk,
)
from host_executor_app.services.runtime_session_engine import (
    BaseRuntimeSessionService,
    RuntimeLaunchConfig,
    RuntimeSessionServiceError,
    RuntimeSessionState,
    _utc_now,
)


@dataclass(slots=True)
class CodexSessionServiceError(RuntimeSessionServiceError):
    """Normalized error raised for Codex session failures."""


@dataclass(slots=True)
class _SessionState(RuntimeSessionState):
    """Internal mutable state for one Codex subprocess."""

    codex_session_id: str | None = None


class CodexSessionService(BaseRuntimeSessionService):
    """Manage in-memory host-side Codex sessions keyed by run id."""

    runtime_label = "Codex"
    cli_label = "Codex CLI"
    sessions_dir_name = "codex-sessions"
    thread_name_prefix = "codex"
    tmux_session_prefix = "tap-run"
    error_cls = CodexSessionServiceError
    read_model = CodexSessionRead
    chunk_model = CodexTerminalChunk
    events_response_model = CodexSessionEventsResponse

    _MULTI_AGENT_FEATURE = "multi_agent"
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

    def _validate_start_workspace(self, *, repo_path: Path, payload: CodexSessionStart) -> None:
        """Validate the prepared Codex workspace before launch."""
        config_path = repo_path / ".codex" / "config.toml"
        task_path = repo_path / "TASK.md"
        if not config_path.exists():
            raise CodexSessionServiceError(409, "Workspace is missing `.codex/config.toml`.")
        if not task_path.exists():
            raise CodexSessionServiceError(409, "Workspace is missing `TASK.md`.")

    def _prepare_start_launch(
        self,
        *,
        repo_path: Path,
        payload: CodexSessionStart,
    ) -> RuntimeLaunchConfig:
        """Build the Codex launch config for one fresh run."""
        command = self._build_command(repo_path=repo_path, payload=payload)
        codex_home = self._prepare_codex_home(repo_path=repo_path)
        codex_home_value = str(codex_home)
        return RuntimeLaunchConfig(
            command=command,
            env_overrides={"CODEX_HOME": codex_home_value},
            script_exports={"CODEX_HOME": codex_home_value},
        )

    def _prepare_resume_launch(
        self,
        state: _SessionState,
        repo_path: Path,
        *,
        auto_resume: bool,
    ) -> RuntimeLaunchConfig:
        """Build the Codex launch config used to resume one interrupted run."""
        codex_home = self._codex_home_path(repo_path=repo_path)
        if not codex_home.exists():
            if auto_resume:
                raise CodexSessionServiceError(
                    409,
                    "Automatic semantic resume is unavailable because CODEX_HOME is missing.",
                )
            raise CodexSessionServiceError(
                409,
                "Persisted CODEX_HOME is missing for this run. Semantic resume is unavailable.",
            )

        command = self._build_resume_command(state.codex_session_id or "")
        codex_home_value = str(codex_home)
        return RuntimeLaunchConfig(
            command=command,
            env_overrides={"CODEX_HOME": codex_home_value},
            script_exports={"CODEX_HOME": codex_home_value},
        )

    def _build_started_state(
        self,
        *,
        payload: CodexSessionStart,
        repo_path: Path,
        storage_dir: Path,
        launch: RuntimeLaunchConfig,
        process,
        master_fd: int | None,
        pid: int | None,
        transport_kind: str,
        transport_ref: str | None,
    ) -> _SessionState:
        """Construct the in-memory state for one started Codex run."""
        return _SessionState(
            run_id=payload.run_id,
            workspace_id=payload.workspace_id,
            repo_path=str(repo_path),
            command=launch.command,
            storage_dir=str(storage_dir),
            process=process,
            master_fd=master_fd,
            started_at=_utc_now(),
            pid=pid,
            transport_kind=transport_kind,
            transport_ref=transport_ref,
        )

    def _build_state_from_session(
        self,
        *,
        session: CodexSessionRead,
        storage_dir: Path,
        chunks: list[CodexTerminalChunk],
    ) -> _SessionState:
        """Restore Codex runtime state from persisted public session data."""
        return _SessionState(
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
            codex_session_id=session.codex_session_id or session.runtime_session_id,
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

    def _get_runtime_session_id(self, state: _SessionState) -> str | None:
        """Return the persisted Codex thread id when available."""
        return state.codex_session_id

    def _after_chunk_appended(self, state: _SessionState) -> None:
        """Update the in-memory Codex session id from structured JSONL output."""
        super()._after_chunk_appended(state)
        if state.codex_session_id is None:
            state.codex_session_id = self._derive_codex_session_id(state.chunks)

    @classmethod
    def _build_command(cls, *, repo_path: Path, payload: CodexSessionStart) -> list[str]:
        """Return the Codex CLI command for one run."""
        command = [
            "codex",
            "-c",
            "mcp_servers={}",
            "--ask-for-approval",
            "never",
            "exec",
            "--enable",
            cls._MULTI_AGENT_FEATURE,
            "--json",
            "--color",
            "always",
            "--cd",
            str(repo_path),
            "--sandbox",
            payload.sandbox_mode,
            "-",
        ]
        if payload.model:
            command.extend(["--model", payload.model])
        if payload.model_reasoning_effort:
            command.extend(
                [
                    "-c",
                    f"model_reasoning_effort={json.dumps(payload.model_reasoning_effort)}",
                ]
            )
        return command

    @classmethod
    def _build_resume_command(cls, codex_session_id: str) -> list[str]:
        """Return the Codex CLI command used to resume one persisted session."""
        return [
            "codex",
            "-c",
            "mcp_servers={}",
            "--ask-for-approval",
            "never",
            "exec",
            "resume",
            "--enable",
            cls._MULTI_AGENT_FEATURE,
            "--json",
            "--color",
            "always",
            codex_session_id,
            cls._RESUME_PROMPT,
        ]

    @staticmethod
    def _prepare_codex_home(*, repo_path: Path) -> Path:
        """Build a clean per-workspace CODEX_HOME without inheriting global MCP config."""
        default_codex_home = Path.home() / ".codex"
        source_auth = default_codex_home / "auth.json"
        if not source_auth.exists():
            raise CodexSessionServiceError(
                409,
                "Codex auth.json was not found in ~/.codex. Run `codex login` and retry.",
            )

        codex_home = CodexSessionService._codex_home_path(repo_path=repo_path)
        codex_home.mkdir(parents=True, exist_ok=True)
        (codex_home / "skills" / ".system").mkdir(parents=True, exist_ok=True)
        (codex_home / "shell_snapshots").mkdir(parents=True, exist_ok=True)
        (codex_home / "log").mkdir(parents=True, exist_ok=True)
        (codex_home / "tmp").mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_auth, codex_home / "auth.json")

        config_path = codex_home / "config.toml"
        if config_path.exists():
            config_path.unlink()

        return codex_home

    @staticmethod
    def _codex_home_path(*, repo_path: Path) -> Path:
        """Return the per-workspace CODEX_HOME directory."""
        return repo_path.parent / "codex-home"

    @staticmethod
    def _derive_summary(chunks: list[CodexTerminalChunk]) -> str | None:
        """Return the latest explicit turn summary from structured Codex JSON output."""
        last_agent_message: str | None = None
        last_completed_turn_summary: str | None = None

        for payload in CodexSessionService._iter_json_objects(chunks):
            payload_type = payload.get("type")
            if payload_type == "turn.started":
                last_agent_message = None
                continue

            if payload_type == "item.completed":
                item = payload.get("item")
                if not isinstance(item, dict) or item.get("type") != "agent_message":
                    continue
                message = item.get("text")
                if isinstance(message, str) and message.strip():
                    last_agent_message = message.strip()
                continue

            if payload_type != "turn.completed":
                continue

            explicit_summary = CodexSessionService._extract_turn_completed_summary(payload)
            if explicit_summary:
                last_completed_turn_summary = CodexSessionService._normalize_summary_candidate(
                    explicit_summary
                )
            elif last_agent_message:
                last_completed_turn_summary = CodexSessionService._normalize_summary_candidate(
                    last_agent_message
                )

        return last_completed_turn_summary

    @staticmethod
    def _extract_turn_completed_summary(payload: dict[str, object]) -> str | None:
        """Return an explicit human summary from one turn.completed payload when present."""
        for key in ("summary", "text", "message"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

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
        """Return whether the candidate looks like code or a raw file dump instead of prose."""
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
    def _iter_json_objects(chunks: list[CodexTerminalChunk]):
        """Yield parsed JSON objects reconstructed from chunked Codex JSONL output."""
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
    def _derive_error_message(cls, chunks: list[CodexTerminalChunk], *, exit_code: int) -> str:
        """Extract a readable failure message from Codex terminal output."""
        lines: list[str] = []
        for chunk in chunks:
            lines.extend(chunk.text.splitlines())

        for line in reversed(lines):
            stripped = line.strip()
            if not stripped:
                continue
            message = cls._extract_message_from_json_line(stripped)
            if message:
                return message
            if "missing YAML frontmatter delimited by ---" in stripped:
                return stripped
            if stripped.startswith("ERROR "):
                match = re.search(r"ERROR .*?: (.+)$", stripped)
                if match:
                    return match.group(1).strip()
                return stripped

        return f"Codex CLI exited with code {exit_code}."

    @classmethod
    def _extract_message_from_json_line(cls, line: str) -> str | None:
        """Parse one JSONL line and return nested message text when present."""
        if not line.startswith("{"):
            return None
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return None
        return cls._extract_message_from_payload(payload)

    @classmethod
    def _extract_message_from_payload(cls, payload: object) -> str | None:
        """Return the most useful message from a nested Codex event payload."""
        if isinstance(payload, str):
            normalized = payload.strip()
            if not normalized:
                return None
            nested = cls._extract_message_from_embedded_json(normalized)
            return nested or normalized

        if not isinstance(payload, dict):
            return None

        error_value = payload.get("error")
        if error_value is not None:
            nested_error = cls._extract_message_from_payload(error_value)
            if nested_error:
                return nested_error

        message_value = payload.get("message")
        if isinstance(message_value, str) and message_value.strip():
            nested = cls._extract_message_from_embedded_json(message_value.strip())
            return nested or message_value.strip()

        detail_value = payload.get("detail")
        if isinstance(detail_value, str) and detail_value.strip():
            return detail_value.strip()

        return None

    @classmethod
    def _extract_message_from_embedded_json(cls, value: str) -> str | None:
        """Parse nested serialized JSON strings used by Codex error events."""
        if not value.startswith("{"):
            return None
        try:
            payload = json.loads(value)
        except json.JSONDecodeError:
            return None
        nested = cls._extract_message_from_payload(payload)
        if nested == value:
            return None
        return nested

    @classmethod
    def _derive_usage_metrics(
        cls,
        chunks: list[CodexTerminalChunk],
    ) -> tuple[int | None, int | None]:
        """Return the latest token usage reported by Codex turn completion events."""
        input_tokens: int | None = None
        output_tokens: int | None = None

        for payload in cls._iter_json_objects(chunks):
            parsed = cls._extract_usage_from_payload(payload)
            if parsed is not None:
                input_tokens, output_tokens = parsed

        return input_tokens, output_tokens

    @classmethod
    def _extract_usage_from_json_line(cls, line: str) -> tuple[int | None, int | None] | None:
        """Parse one JSONL line and return token usage when available."""
        if not line.startswith("{"):
            return None

        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return None

        if not isinstance(payload, dict):
            return None
        return cls._extract_usage_from_payload(payload)

    @staticmethod
    def _extract_usage_from_payload(
        payload: dict[str, object]
    ) -> tuple[int | None, int | None] | None:
        """Return token usage from one parsed turn.completed payload when available."""
        if payload.get("type") != "turn.completed":
            return None

        usage = payload.get("usage")
        if not isinstance(usage, dict):
            return None

        raw_input = usage.get("input_tokens")
        raw_output = usage.get("output_tokens")

        input_tokens = raw_input if isinstance(raw_input, int) else None
        output_tokens = raw_output if isinstance(raw_output, int) else None

        if input_tokens is None and output_tokens is None:
            return None
        return input_tokens, output_tokens

    @classmethod
    def _derive_codex_session_id(cls, chunks: list[CodexTerminalChunk]) -> str | None:
        """Return the Codex thread/session id when it appears in terminal JSONL."""
        session_id: str | None = None

        for payload in cls._iter_json_objects(chunks):
            parsed = cls._extract_session_id_from_payload(payload)
            if parsed is not None:
                session_id = parsed

        return session_id

    @staticmethod
    def _extract_session_id_from_json_line(line: str) -> str | None:
        """Parse one Codex JSONL line and extract thread.started.thread_id when present."""
        if not line.startswith("{"):
            return None

        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return None

        if not isinstance(payload, dict) or payload.get("type") != "thread.started":
            return None

        thread_id = payload.get("thread_id")
        if isinstance(thread_id, str) and thread_id.strip():
            return thread_id.strip()
        return None

    @classmethod
    def _extract_session_id_from_payload(cls, payload: dict[str, object]) -> str | None:
        """Return thread.started.thread_id from an already parsed payload when present."""
        if payload.get("type") != "thread.started":
            return None
        thread_id = payload.get("thread_id")
        if isinstance(thread_id, str) and thread_id.strip():
            return thread_id.strip()
        return None

    @staticmethod
    def _to_read(state: _SessionState) -> CodexSessionRead:
        """Convert internal state into a public API payload."""
        input_tokens, output_tokens = CodexSessionService._derive_usage_metrics(state.chunks)
        return CodexSessionRead(
            run_id=state.run_id,
            workspace_id=state.workspace_id,
            repo_path=state.repo_path,
            command=state.command,
            status=state.status,  # type: ignore[arg-type]
            pid=state.pid,
            exit_code=state.exit_code,
            error_message=state.error_message,
            summary_text=state.summary_text,
            runtime_session_id=state.codex_session_id,
            codex_session_id=state.codex_session_id,
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
