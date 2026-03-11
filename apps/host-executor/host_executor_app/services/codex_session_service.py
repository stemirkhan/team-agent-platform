"""Host-side Codex PTY session management."""

from __future__ import annotations

import json
import os
import pty
import re
import shutil
import signal
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from host_executor_app.schemas.codex import (
    CodexSessionEventsResponse,
    CodexSessionRead,
    CodexSessionStart,
    CodexTerminalChunk,
)
from host_executor_app.services.workspace_service import WorkspaceService, WorkspaceServiceError


@dataclass(slots=True)
class CodexSessionServiceError(Exception):
    """Normalized error raised for Codex session failures."""

    status_code: int
    detail: str


@dataclass(slots=True)
class _SessionState:
    """Internal mutable state for one Codex subprocess."""

    run_id: str
    workspace_id: str
    repo_path: str
    command: list[str]
    started_at: str
    storage_dir: str
    process: subprocess.Popen[bytes] | None = None
    master_fd: int | None = None
    status: str = "running"
    pid: int | None = None
    exit_code: int | None = None
    error_message: str | None = None
    summary_text: str | None = None
    finished_at: str | None = None
    cancel_requested: bool = False
    chunks: list[CodexTerminalChunk] = field(default_factory=list)


class CodexSessionService:
    """Manage in-memory host-side Codex sessions keyed by run id."""

    def __init__(self) -> None:
        self.workspace_service = WorkspaceService()
        self.sessions_root = self.workspace_service.workspace_root.parent / "codex-sessions"
        self.sessions_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._sessions: dict[str, _SessionState] = {}

    def start_session(self, payload: CodexSessionStart) -> CodexSessionRead:
        """Start a new Codex subprocess for one prepared workspace."""
        with self._lock:
            existing = self._sessions.get(payload.run_id)
            if existing is not None:
                if existing.status == "running":
                    raise CodexSessionServiceError(
                        409,
                        "Codex session is already running for this run.",
                    )
                raise CodexSessionServiceError(
                    409,
                    "Codex session already exists for this run.",
                )

        workspace = self._get_workspace(payload.workspace_id)
        repo_path = Path(workspace.repo_path)
        config_path = repo_path / ".codex" / "config.toml"
        task_path = repo_path / "TASK.md"
        if not config_path.exists():
            raise CodexSessionServiceError(409, "Workspace is missing `.codex/config.toml`.")
        if not task_path.exists():
            raise CodexSessionServiceError(409, "Workspace is missing `TASK.md`.")

        command = self._build_command(repo_path=repo_path, payload=payload)
        codex_home = self._prepare_codex_home(repo_path=repo_path)
        process, master_fd = self._spawn_process(
            command=command,
            repo_path=repo_path,
            prompt_text=payload.prompt_text,
            codex_home=codex_home,
        )
        storage_dir = self._session_storage_dir(payload.run_id)
        storage_dir.mkdir(parents=True, exist_ok=True)
        state = _SessionState(
            run_id=payload.run_id,
            workspace_id=payload.workspace_id,
            repo_path=str(repo_path),
            command=command,
            storage_dir=str(storage_dir),
            process=process,
            master_fd=master_fd,
            started_at=_utc_now(),
            pid=process.pid,
        )

        with self._lock:
            self._sessions[payload.run_id] = state
            self._persist_state(state)

        reader_thread = threading.Thread(
            target=self._reader_loop,
            args=(payload.run_id,),
            daemon=True,
            name=f"codex-reader-{payload.run_id}",
        )
        waiter_thread = threading.Thread(
            target=self._wait_loop,
            args=(payload.run_id,),
            daemon=True,
            name=f"codex-wait-{payload.run_id}",
        )
        reader_thread.start()
        waiter_thread.start()
        return self._to_read(state)

    def get_session(self, run_id: str) -> CodexSessionRead:
        """Return one existing session."""
        state = self._get_state(run_id)
        return self._to_read(state)

    def get_events(self, run_id: str, offset: int) -> CodexSessionEventsResponse:
        """Return terminal output chunks after the given offset."""
        state = self._get_state(run_id)
        items = [chunk for chunk in state.chunks if chunk.offset >= offset]
        return CodexSessionEventsResponse(
            session=self._to_read(state),
            items=items,
            next_offset=len(state.chunks),
        )

    def cancel_session(self, run_id: str) -> CodexSessionRead:
        """Request graceful termination for one running session."""
        state = self._get_state(run_id)
        if state.status != "running":
            return self._to_read(state)

        state.cancel_requested = True
        self._persist_state(state)
        if (
            state.process is not None
            and state.process.poll() is None
            and state.process.pid is not None
        ):
            try:
                os.killpg(state.process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            except OSError as exc:
                raise CodexSessionServiceError(
                    503,
                    f"Failed to cancel Codex session: {exc}",
                ) from exc
        return self._to_read(state)

    def _get_workspace(self, workspace_id: str):
        """Return workspace metadata or normalize workspace errors."""
        try:
            return self.workspace_service.get_workspace(workspace_id)
        except WorkspaceServiceError as exc:
            raise CodexSessionServiceError(exc.status_code, exc.detail) from exc

    @staticmethod
    def _build_command(*, repo_path: Path, payload: CodexSessionStart) -> list[str]:
        """Return the Codex CLI command for one run."""
        command = [
            "codex",
            "-c",
            "mcp_servers={}",
            "--ask-for-approval",
            "never",
            "exec",
            "--json",
            "--color",
            "always",
            "--cd",
            str(repo_path),
            "--sandbox",
            payload.sandbox_mode,
            "--ephemeral",
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

    def _spawn_process(
        self,
        *,
        command: list[str],
        repo_path: Path,
        prompt_text: str,
        codex_home: Path,
    ) -> tuple[subprocess.Popen[bytes], int]:
        """Spawn a PTY-backed Codex subprocess and write the initial prompt."""
        master_fd, slave_fd = pty.openpty()
        env = os.environ.copy()
        env["CODEX_HOME"] = str(codex_home)
        env.setdefault("TERM", "xterm-256color")
        env.setdefault("COLORTERM", "truecolor")
        env["CLICOLOR"] = "1"
        env["CLICOLOR_FORCE"] = "1"
        env["FORCE_COLOR"] = "1"
        env["PY_COLORS"] = "1"
        try:
            process = subprocess.Popen(
                command,
                cwd=str(repo_path),
                stdin=subprocess.PIPE,
                stdout=slave_fd,
                stderr=slave_fd,
                text=False,
                start_new_session=True,
                env=env,
            )
        except FileNotFoundError as exc:
            os.close(master_fd)
            os.close(slave_fd)
            raise CodexSessionServiceError(503, "Codex CLI is not installed on the host.") from exc
        except OSError as exc:
            os.close(master_fd)
            os.close(slave_fd)
            raise CodexSessionServiceError(503, f"Failed to launch Codex CLI: {exc}") from exc
        finally:
            os.close(slave_fd)

        try:
            if process.stdin is not None:
                process.stdin.write(prompt_text.encode("utf-8"))
                process.stdin.close()
        except OSError as exc:
            os.close(master_fd)
            raise CodexSessionServiceError(
                503,
                f"Failed to send prompt to Codex CLI: {exc}",
            ) from exc
        return process, master_fd

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

        codex_home = repo_path.parent / "codex-home"
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

    def _reader_loop(self, run_id: str) -> None:
        """Read PTY output and append it to the in-memory session buffer."""
        state = self._get_state(run_id)
        while True:
            if state.master_fd is None:
                break
            try:
                data = os.read(state.master_fd, 4096)
            except OSError:
                break
            if not data:
                break
            text = data.decode("utf-8", errors="replace")
            with self._lock:
                state = self._sessions.get(run_id) or state
                chunk = CodexTerminalChunk(
                    offset=len(state.chunks),
                    text=text,
                    created_at=_utc_now(),
                )
                state.chunks.append(chunk)
                self._persist_chunk(state, chunk)
                self._persist_state(state)

        try:
            if state.master_fd is not None:
                os.close(state.master_fd)
        except OSError:
            pass

    def _wait_loop(self, run_id: str) -> None:
        """Wait for process exit and finalize the in-memory session state."""
        state = self._get_state(run_id)
        if state.process is None:
            return
        exit_code = state.process.wait()
        with self._lock:
            state = self._sessions.get(run_id) or state
            state.exit_code = exit_code
            state.finished_at = _utc_now()
            if state.cancel_requested:
                state.status = "cancelled"
            elif exit_code == 0:
                state.status = "completed"
            else:
                state.status = "failed"
            state.summary_text = self._derive_summary(state.chunks)
            if state.status == "failed" and not state.error_message:
                state.error_message = self._derive_error_message(state.chunks, exit_code=exit_code)
            self._persist_state(state)

    def _get_state(self, run_id: str) -> _SessionState:
        """Return mutable session state by run id or raise 404."""
        with self._lock:
            state = self._sessions.get(run_id)
            if state is not None:
                return state

        state = self._load_persisted_state(run_id)
        if state is None:
            raise CodexSessionServiceError(404, "Codex session not found.")

        with self._lock:
            existing = self._sessions.get(run_id)
            if existing is not None:
                return existing
            self._sessions[run_id] = state
            return state

    def _load_persisted_state(self, run_id: str) -> _SessionState | None:
        """Load a persisted session snapshot from disk and recover stale running states."""
        metadata_path = self._session_storage_dir(run_id) / "session.json"
        if not metadata_path.exists():
            return None

        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CodexSessionServiceError(
                500,
                f"Persisted Codex session state is corrupted for run `{run_id}`.",
            ) from exc

        try:
            session = CodexSessionRead.model_validate(payload)
        except Exception as exc:  # noqa: BLE001
            raise CodexSessionServiceError(
                500,
                f"Persisted Codex session state is invalid for run `{run_id}`.",
            ) from exc

        state = _SessionState(
            run_id=session.run_id,
            workspace_id=session.workspace_id,
            repo_path=session.repo_path,
            command=session.command,
            storage_dir=str(self._session_storage_dir(run_id)),
            started_at=session.started_at,
            status=session.status,
            pid=session.pid,
            exit_code=session.exit_code,
            error_message=session.error_message,
            summary_text=session.summary_text,
            finished_at=session.finished_at,
            chunks=self._load_persisted_chunks(run_id),
        )

        if state.status == "running":
            return self._recover_interrupted_running_state(state)

        return state

    def _load_persisted_chunks(self, run_id: str) -> list[CodexTerminalChunk]:
        """Load persisted terminal chunks from disk."""
        chunks_path = self._session_storage_dir(run_id) / "chunks.jsonl"
        if not chunks_path.exists():
            return []

        items: list[CodexTerminalChunk] = []
        for raw_line in chunks_path.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip():
                continue
            try:
                payload = json.loads(raw_line)
                items.append(CodexTerminalChunk.model_validate(payload))
            except Exception:  # noqa: BLE001
                continue
        return items

    def _recover_interrupted_running_state(self, state: _SessionState) -> _SessionState:
        """Convert a persisted running session into a deterministic failed state after restart."""
        if state.pid is not None and self._process_exists(state.pid):
            try:
                os.killpg(state.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            except OSError:
                pass

        state.status = "failed"
        state.finished_at = _utc_now()
        state.error_message = (
            "Host executor restarted while Codex was running. "
            "The live session cannot be resumed in the current MVP."
        )
        if state.summary_text is None:
            state.summary_text = self._derive_summary(state.chunks)
        self._persist_state(state)
        return state

    def _persist_state(self, state: _SessionState) -> None:
        """Persist the latest public session snapshot to disk."""
        storage_dir = Path(state.storage_dir)
        storage_dir.mkdir(parents=True, exist_ok=True)
        (storage_dir / "session.json").write_text(
            json.dumps(self._to_read(state).model_dump(), ensure_ascii=True, indent=2),
            encoding="utf-8",
        )

    def _persist_chunk(self, state: _SessionState, chunk: CodexTerminalChunk) -> None:
        """Append one terminal chunk to the persisted JSONL log."""
        storage_dir = Path(state.storage_dir)
        storage_dir.mkdir(parents=True, exist_ok=True)
        with (storage_dir / "chunks.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(chunk.model_dump(), ensure_ascii=True))
            handle.write("\n")

    def _session_storage_dir(self, run_id: str) -> Path:
        """Return the filesystem directory used to persist one run session."""
        return self.sessions_root / run_id

    @staticmethod
    def _process_exists(pid: int) -> bool:
        """Return whether a pid currently exists in the local process table."""
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        return True

    @staticmethod
    def _derive_summary(chunks: list[CodexTerminalChunk]) -> str | None:
        """Return a small final summary from accumulated terminal chunks."""
        for chunk in reversed(chunks):
            text = chunk.text.strip()
            if text:
                return text[-4000:]
        return None

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
    def _derive_usage_metrics(cls, chunks: list[CodexTerminalChunk]) -> tuple[int | None, int | None]:
        """Return the latest token usage reported by Codex turn completion events."""
        buffer = ""
        input_tokens: int | None = None
        output_tokens: int | None = None

        for chunk in chunks:
            combined = f"{buffer}{chunk.text}".replace("\r\n", "\n")
            lines = combined.split("\n")
            buffer = lines.pop() or ""

            for line in lines:
                parsed = cls._extract_usage_from_json_line(line.strip())
                if parsed is not None:
                    input_tokens, output_tokens = parsed

        if buffer.strip():
            parsed = cls._extract_usage_from_json_line(buffer.strip())
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

        if not isinstance(payload, dict) or payload.get("type") != "turn.completed":
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
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            started_at=state.started_at,
            finished_at=state.finished_at,
            last_output_offset=len(state.chunks),
        )


def _utc_now() -> str:
    """Return a stable UTC timestamp."""
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
