"""Host-side Codex PTY session management."""

from __future__ import annotations

import json
import os
import pty
import re
import shlex
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
    codex_session_id: str | None = None
    transport_kind: str = "pty"
    transport_ref: str | None = None
    resume_attempt_count: int = 0
    interrupted_at: str | None = None
    resumable: bool = False
    recovered_from_restart: bool = False
    output_bytes_read: int = 0
    finished_at: str | None = None
    cancel_requested: bool = False
    chunks: list[CodexTerminalChunk] = field(default_factory=list)


class CodexSessionService:
    """Manage in-memory host-side Codex sessions keyed by run id."""

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

        storage_dir = self._session_storage_dir(payload.run_id)
        storage_dir.mkdir(parents=True, exist_ok=True)
        self._reset_transport_files(storage_dir)
        command = self._build_command(repo_path=repo_path, payload=payload)
        codex_home = self._prepare_codex_home(repo_path=repo_path)
        use_tmux = self._tmux_available()
        process: subprocess.Popen[bytes] | None = None
        master_fd: int | None = None
        pid: int | None = None
        transport_kind = "tmux" if use_tmux else "pty"
        transport_ref: str | None = None

        if use_tmux:
            transport_ref = self._spawn_tmux_session(
                run_id=payload.run_id,
                command=command,
                repo_path=repo_path,
                codex_home=codex_home,
                storage_dir=storage_dir,
                stdin_payload=payload.prompt_text.encode("utf-8"),
            )
        else:
            process, master_fd = self._spawn_process(
                command=command,
                repo_path=repo_path,
                codex_home=codex_home,
                stdin_payload=payload.prompt_text.encode("utf-8"),
            )
            pid = process.pid
            transport_ref = str(process.pid)

        state = _SessionState(
            run_id=payload.run_id,
            workspace_id=payload.workspace_id,
            repo_path=str(repo_path),
            command=command,
            storage_dir=str(storage_dir),
            process=process,
            master_fd=master_fd,
            started_at=_utc_now(),
            pid=pid,
            transport_kind=transport_kind,
            transport_ref=transport_ref,
        )

        with self._lock:
            self._sessions[payload.run_id] = state
            self._persist_state(state)

        if transport_kind == "pty":
            self._start_background_threads(payload.run_id)
        return self._to_read(state)

    def resume_session(self, run_id: str) -> CodexSessionRead:
        """Resume an interrupted Codex session by reusing the persisted CODEX_HOME."""
        state = self._get_state(run_id)
        if state.status in {"running", "resuming"}:
            raise CodexSessionServiceError(409, "Codex session is already active for this run.")
        if state.status != "interrupted":
            raise CodexSessionServiceError(
                409,
                "Only interrupted Codex sessions can be resumed.",
            )
        if not state.resumable or not state.codex_session_id:
            raise CodexSessionServiceError(
                409,
                "Codex session is not resumable for this run.",
            )
        if state.pid is not None and self._process_exists(state.pid):
            raise CodexSessionServiceError(
                409,
                "Original Codex pid is still alive. "
                "Resume is blocked to avoid duplicate execution.",
            )

        repo_path = Path(state.repo_path)
        codex_home = self._codex_home_path(repo_path=repo_path)
        if not codex_home.exists():
            raise CodexSessionServiceError(
                409,
                "Persisted CODEX_HOME is missing for this run. Semantic resume is unavailable.",
            )

        command = self._build_resume_command(state.codex_session_id)
        use_tmux = self._tmux_available()
        process: subprocess.Popen[bytes] | None = None
        master_fd: int | None = None
        pid: int | None = None
        transport_kind = "tmux" if use_tmux else "pty"
        transport_ref: str | None = None

        self._reset_transport_files(Path(state.storage_dir), preserve_chunks=True)
        if use_tmux:
            transport_ref = self._spawn_tmux_session(
                run_id=run_id,
                command=command,
                repo_path=repo_path,
                codex_home=codex_home,
                storage_dir=Path(state.storage_dir),
                stdin_payload=None,
            )
        else:
            process, master_fd = self._spawn_process(
                command=command,
                repo_path=repo_path,
                codex_home=codex_home,
                stdin_payload=None,
            )
            pid = process.pid
            transport_ref = str(process.pid)

        with self._lock:
            state = self._sessions.get(run_id) or state
            state.command = command
            state.process = process
            state.master_fd = master_fd
            state.status = "resuming"
            state.pid = pid
            state.transport_kind = transport_kind
            state.transport_ref = transport_ref
            state.exit_code = None
            state.error_message = None
            state.finished_at = None
            state.interrupted_at = None
            state.cancel_requested = False
            state.resume_attempt_count += 1
            state.resumable = False
            state.output_bytes_read = 0
            self._persist_state(state)

        if transport_kind == "pty":
            self._start_background_threads(run_id)
        return self._to_read(state)

    def get_session(self, run_id: str) -> CodexSessionRead:
        """Return one existing session."""
        state = self._get_state(run_id)
        self._refresh_state(state)
        return self._to_read(state)

    def get_events(self, run_id: str, offset: int) -> CodexSessionEventsResponse:
        """Return terminal output chunks after the given offset."""
        state = self._get_state(run_id)
        self._refresh_state(state)
        items = [chunk for chunk in state.chunks if chunk.offset >= offset]
        return CodexSessionEventsResponse(
            session=self._to_read(state),
            items=items,
            next_offset=len(state.chunks),
        )

    def cancel_session(self, run_id: str) -> CodexSessionRead:
        """Request graceful termination for one running session."""
        state = self._get_state(run_id)
        if state.status not in {"running", "resuming"}:
            return self._to_read(state)

        state.cancel_requested = True
        if state.transport_kind == "tmux":
            if state.transport_ref and self._tmux_session_exists(state.transport_ref):
                self._kill_tmux_session(state.transport_ref)
            state.status = "cancelled"
            state.finished_at = _utc_now()
            state.resumable = False
            self._persist_state(state)
            return self._to_read(state)

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

    def _spawn_tmux_session(
        self,
        *,
        run_id: str,
        command: list[str],
        repo_path: Path,
        codex_home: Path,
        storage_dir: Path,
        stdin_payload: bytes | None,
    ) -> str:
        """Start one Codex command inside a detached tmux session."""
        session_name = self._tmux_session_name(run_id)
        self._kill_tmux_session(session_name, ignore_missing=True)

        stdin_path: Path | None = None
        if stdin_payload is not None:
            stdin_path = self._stdin_payload_path(storage_dir)
            stdin_path.write_bytes(stdin_payload)

        script_path = self._runner_script_path(storage_dir)
        script_path.write_text(
            self._build_tmux_runner_script(
                command=command,
                codex_home=codex_home,
                stdin_path=stdin_path,
                exit_code_path=self._exit_code_path(storage_dir),
            ),
            encoding="utf-8",
        )
        script_path.chmod(0o700)

        start_command = [
            "tmux",
            "new-session",
            "-d",
            "-s",
            session_name,
            "-c",
            str(repo_path),
            f"sh -lc 'sleep 0.2; exec sh {shlex.quote(str(script_path))}'",
        ]
        self._run_tmux(start_command)
        self._run_tmux(
            [
                "tmux",
                "pipe-pane",
                "-t",
                f"{session_name}:0.0",
                "-o",
                f"cat >> {shlex.quote(str(self._raw_output_path(storage_dir)))}",
            ]
        )
        return session_name

    def _refresh_state(self, state: _SessionState) -> None:
        """Synchronize transport-backed session state before reading it."""
        if state.transport_kind == "tmux":
            self._refresh_tmux_state(state)

    def _refresh_tmux_state(self, state: _SessionState) -> None:
        """Update one tmux-backed session from its persisted raw output and session liveness."""
        self._sync_tmux_output(state)

        session_name = state.transport_ref
        session_is_alive = bool(session_name) and self._tmux_session_exists(session_name)
        if session_is_alive:
            if state.status == "resuming":
                state.status = "running"
            state.resumable = False
            state.interrupted_at = None
            if state.finished_at and state.status in {"running", "resuming"}:
                state.finished_at = None
            self._persist_state(state)
            return

        exit_code = self._read_exit_code(state)
        if exit_code is not None:
            self._finalize_tmux_state(state, exit_code=exit_code)
            return

        if state.status in {"running", "resuming"}:
            self._recover_lost_tmux_state(state)

    def _sync_tmux_output(self, state: _SessionState) -> None:
        """Append any new raw tmux pane bytes into persisted terminal chunks."""
        raw_output_path = self._raw_output_path(Path(state.storage_dir))
        if not raw_output_path.exists():
            return

        with raw_output_path.open("rb") as handle:
            handle.seek(state.output_bytes_read)
            data = handle.read()

        if not data:
            return

        text = data.decode("utf-8", errors="replace")
        chunk = CodexTerminalChunk(
            offset=len(state.chunks),
            text=text,
            created_at=_utc_now(),
        )
        state.chunks.append(chunk)
        state.output_bytes_read += len(data)
        if state.status == "resuming":
            state.status = "running"
        if state.codex_session_id is None:
            state.codex_session_id = self._derive_codex_session_id(state.chunks)
        self._persist_chunk(state, chunk)
        self._persist_state(state)

    def _finalize_tmux_state(self, state: _SessionState, *, exit_code: int) -> None:
        """Persist the final state of one finished tmux-backed session."""
        state.exit_code = exit_code
        if state.finished_at is None:
            state.finished_at = _utc_now()
        if state.cancel_requested or state.status == "cancelled":
            state.status = "cancelled"
        elif exit_code == 0:
            state.status = "completed"
        else:
            state.status = "failed"
        state.interrupted_at = None
        state.resumable = False
        state.summary_text = self._derive_summary(state.chunks)
        if state.status == "failed" and not state.error_message:
            state.error_message = self._derive_error_message(state.chunks, exit_code=exit_code)
        self._persist_state(state)

    def _recover_lost_tmux_state(self, state: _SessionState) -> None:
        """Downgrade a tmux-backed session into an interrupted or failed state."""
        state.process = None
        state.master_fd = None
        state.recovered_from_restart = True
        state.finished_at = _utc_now()
        state.interrupted_at = state.finished_at

        if state.codex_session_id:
            resumed = self._attempt_auto_semantic_resume(
                state,
                reason=(
                    "tmux transport is no longer attached to the Codex session "
                    "after host executor recovery."
                ),
            )
            if resumed.status in {"running", "resuming"}:
                return
        else:
            state.status = "failed"
            state.resumable = False
            state.error_message = (
                "tmux transport was lost and no resumable Codex session id was captured."
            )

        if state.summary_text is None:
            state.summary_text = self._derive_summary(state.chunks)
        self._persist_state(state)

    @staticmethod
    def _build_tmux_runner_script(
        *,
        command: list[str],
        codex_home: Path,
        stdin_path: Path | None,
        exit_code_path: Path,
    ) -> str:
        """Render the shell script executed inside the detached tmux session."""
        stdin_line = (
            f"cat {shlex.quote(str(stdin_path))} | {shlex.join(command)}"
            if stdin_path is not None
            else shlex.join(command)
        )
        return "\n".join(
            [
                "#!/bin/sh",
                f"export CODEX_HOME={shlex.quote(str(codex_home))}",
                "export TERM=${TERM:-xterm-256color}",
                "export COLORTERM=${COLORTERM:-truecolor}",
                "export CLICOLOR=1",
                "export CLICOLOR_FORCE=1",
                "export FORCE_COLOR=1",
                "export PY_COLORS=1",
                stdin_line,
                "exit_code=$?",
                f"printf '%s' \"$exit_code\" > {shlex.quote(str(exit_code_path))}",
                "exit \"$exit_code\"",
                "",
            ]
        )

    def _start_background_threads(self, run_id: str) -> None:
        """Start reader and waiter threads for one active session."""
        reader_thread = threading.Thread(
            target=self._reader_loop,
            args=(run_id,),
            daemon=True,
            name=f"codex-reader-{run_id}",
        )
        waiter_thread = threading.Thread(
            target=self._wait_loop,
            args=(run_id,),
            daemon=True,
            name=f"codex-wait-{run_id}",
        )
        reader_thread.start()
        waiter_thread.start()

    def _spawn_process(
        self,
        *,
        command: list[str],
        repo_path: Path,
        codex_home: Path,
        stdin_payload: bytes | None,
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
                if stdin_payload is not None:
                    process.stdin.write(stdin_payload)
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
    def _tmux_available() -> bool:
        """Return whether tmux is available in PATH."""
        return shutil.which("tmux") is not None

    @staticmethod
    def _tmux_session_name(run_id: str) -> str:
        """Return a stable tmux session name for one run."""
        return f"tap-run-{run_id}"

    @staticmethod
    def _raw_output_path(storage_dir: Path) -> Path:
        """Return the raw tmux pane output file."""
        return storage_dir / "pane.log"

    @staticmethod
    def _exit_code_path(storage_dir: Path) -> Path:
        """Return the file where the runner script writes its exit code."""
        return storage_dir / "exit-code.txt"

    @staticmethod
    def _stdin_payload_path(storage_dir: Path) -> Path:
        """Return the persisted stdin payload file used for one run."""
        return storage_dir / "stdin.txt"

    @staticmethod
    def _runner_script_path(storage_dir: Path) -> Path:
        """Return the shell wrapper path for one tmux-backed Codex run."""
        return storage_dir / "launch.sh"

    def _reset_transport_files(self, storage_dir: Path, *, preserve_chunks: bool = False) -> None:
        """Clear raw transport artifacts before a new start or resume attempt."""
        for path in (
            self._raw_output_path(storage_dir),
            self._exit_code_path(storage_dir),
            self._stdin_payload_path(storage_dir),
            self._runner_script_path(storage_dir),
        ):
            if path.exists():
                path.unlink()
        if not preserve_chunks:
            chunks_path = storage_dir / "chunks.jsonl"
            if chunks_path.exists():
                chunks_path.unlink()

    def _run_tmux(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        """Run one tmux command and normalize transport failures."""
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except FileNotFoundError as exc:
            raise CodexSessionServiceError(503, "tmux is not installed on the host.") from exc
        except OSError as exc:
            raise CodexSessionServiceError(503, f"Failed to launch tmux: {exc}") from exc

        if result.returncode != 0:
            detail = "\n".join(
                chunk
                for chunk in (result.stdout.strip(), result.stderr.strip())
                if chunk
            )
            raise CodexSessionServiceError(503, detail or "tmux command failed.")
        return result

    def _tmux_session_exists(self, session_name: str) -> bool:
        """Return whether one tmux session currently exists."""
        try:
            result = subprocess.run(
                ["tmux", "has-session", "-t", session_name],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (FileNotFoundError, OSError):
            return False
        return result.returncode == 0

    def _kill_tmux_session(self, session_name: str, *, ignore_missing: bool = False) -> None:
        """Terminate one tmux session when it exists."""
        try:
            result = subprocess.run(
                ["tmux", "kill-session", "-t", session_name],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (FileNotFoundError, OSError) as exc:
            if ignore_missing:
                return
            raise CodexSessionServiceError(503, f"Failed to stop tmux session: {exc}") from exc

        if result.returncode != 0 and not ignore_missing:
            detail = "\n".join(
                chunk
                for chunk in (result.stdout.strip(), result.stderr.strip())
                if chunk
            )
            raise CodexSessionServiceError(503, detail or "Failed to stop tmux session.")

    def _read_exit_code(self, state: _SessionState) -> int | None:
        """Return the tmux runner exit code when it was written to disk."""
        exit_code_path = self._exit_code_path(Path(state.storage_dir))
        if not exit_code_path.exists():
            return None
        try:
            value = exit_code_path.read_text(encoding="utf-8").strip()
            return int(value)
        except (OSError, ValueError):
            return None

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
                if state.status == "resuming":
                    state.status = "running"
                if state.codex_session_id is None:
                    state.codex_session_id = self._derive_codex_session_id(state.chunks)
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
            state.interrupted_at = None
            state.resumable = False
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
            if (
                state.transport_kind == "pty"
                and state.process is not None
                and state.status in {"running", "resuming"}
            ):
                self._start_background_threads(run_id)
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
            codex_session_id=session.codex_session_id,
            transport_kind=session.transport_kind,
            transport_ref=session.transport_ref,
            resume_attempt_count=session.resume_attempt_count,
            interrupted_at=session.interrupted_at,
            resumable=session.resumable,
            recovered_from_restart=session.recovered_from_restart,
            output_bytes_read=session.output_bytes_read,
            finished_at=session.finished_at,
            chunks=self._load_persisted_chunks(run_id),
        )

        if state.status in {"running", "resuming"}:
            if state.transport_kind == "tmux":
                return self._recover_tmux_running_state(state)
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
        """Reclassify a stale running session after host executor restart."""
        state.status = "interrupted"
        state.finished_at = _utc_now()
        state.interrupted_at = state.finished_at
        state.recovered_from_restart = True
        state.process = None
        state.master_fd = None

        pid_is_alive = state.pid is not None and self._process_exists(state.pid)
        if pid_is_alive:
            state.resumable = False
            state.error_message = (
                "Host executor restarted while the original Codex pid still appears alive. "
                "PTY reattach is not supported yet, so semantic resume is blocked to avoid "
                "duplicate execution."
            )
        elif state.codex_session_id:
            return self._attempt_auto_semantic_resume(
                state,
                reason=(
                    "Host executor restarted while Codex was running. "
                    "The live PTY session was interrupted."
                ),
            )
        else:
            state.status = "failed"
            state.resumable = False
            state.error_message = (
                "Host executor restarted while Codex was running, "
                "and no resumable Codex session id was captured."
            )

        if state.summary_text is None:
            state.summary_text = self._derive_summary(state.chunks)
        self._persist_state(state)
        return state

    def _recover_tmux_running_state(self, state: _SessionState) -> _SessionState:
        """Recover a persisted tmux-backed session after host executor restart."""
        state.process = None
        state.master_fd = None
        state.recovered_from_restart = True
        self._refresh_tmux_state(state)
        if state.status in {"running", "resuming"}:
            state.error_message = None
            self._persist_state(state)
        return state

    def _attempt_auto_semantic_resume(
        self,
        state: _SessionState,
        *,
        reason: str,
    ) -> _SessionState:
        """Try to auto-resume one interrupted session after host executor restart."""
        if not state.codex_session_id:
            state.resumable = False
            state.error_message = f"{reason} No resumable Codex session id was captured."
            if state.summary_text is None:
                state.summary_text = self._derive_summary(state.chunks)
            self._persist_state(state)
            return state

        repo_path = Path(state.repo_path)
        codex_home = self._codex_home_path(repo_path=repo_path)
        if not codex_home.exists():
            state.resumable = True
            state.error_message = (
                f"{reason} Automatic semantic resume is unavailable because CODEX_HOME is missing."
            )
            if state.summary_text is None:
                state.summary_text = self._derive_summary(state.chunks)
            self._persist_state(state)
            return state

        command = self._build_resume_command(state.codex_session_id)
        use_tmux = self._tmux_available()
        process: subprocess.Popen[bytes] | None = None
        master_fd: int | None = None
        pid: int | None = None
        transport_kind = "tmux" if use_tmux else "pty"
        transport_ref: str | None = None

        self._reset_transport_files(Path(state.storage_dir), preserve_chunks=True)
        try:
            if use_tmux:
                transport_ref = self._spawn_tmux_session(
                    run_id=state.run_id,
                    command=command,
                    repo_path=repo_path,
                    codex_home=codex_home,
                    storage_dir=Path(state.storage_dir),
                    stdin_payload=None,
                )
            else:
                process, master_fd = self._spawn_process(
                    command=command,
                    repo_path=repo_path,
                    codex_home=codex_home,
                    stdin_payload=None,
                )
                pid = process.pid
                transport_ref = str(process.pid)
        except CodexSessionServiceError as exc:
            state.resumable = True
            state.error_message = (
                f"{reason} Automatic semantic resume could not start: {exc.detail}"
            )
            if state.summary_text is None:
                state.summary_text = self._derive_summary(state.chunks)
            self._persist_state(state)
            return state

        state.command = command
        state.process = process
        state.master_fd = master_fd
        state.status = "resuming"
        state.pid = pid
        state.transport_kind = transport_kind
        state.transport_ref = transport_ref
        state.exit_code = None
        state.error_message = (
            f"{reason} Automatic semantic resume started from the persisted Codex session."
        )
        state.finished_at = None
        state.interrupted_at = None
        state.cancel_requested = False
        state.resume_attempt_count += 1
        state.resumable = False
        state.output_bytes_read = 0
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
        if any(marker in lowered for marker in code_markers):
            return True
        return False

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


def _utc_now() -> str:
    """Return a stable UTC timestamp."""
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
