"""Shared host-side runtime session engine for PTY and tmux-backed runtimes."""

from __future__ import annotations

import json
import os
import pty
import shlex
import shutil
import signal
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

from host_executor_app.services.workspace_service import WorkspaceService, WorkspaceServiceError


@dataclass(slots=True)
class RuntimeSessionServiceError(Exception):
    """Normalized error raised for runtime session failures."""

    status_code: int
    detail: str


@dataclass(slots=True)
class RuntimeLaunchConfig:
    """Runtime-specific process launch configuration."""

    command: list[str]
    env_overrides: dict[str, str] = field(default_factory=dict)
    script_exports: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class RuntimeSessionState:
    """Internal mutable state for one host-side runtime subprocess."""

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
    transport_kind: str = "pty"
    transport_ref: str | None = None
    resume_attempt_count: int = 0
    interrupted_at: str | None = None
    resumable: bool = False
    recovered_from_restart: bool = False
    output_bytes_read: int = 0
    finished_at: str | None = None
    cancel_requested: bool = False
    chunks: list[Any] = field(default_factory=list)


class BaseRuntimeSessionService:
    """Shared lifecycle engine for host-side runtime sessions."""

    runtime_label: ClassVar[str]
    cli_label: ClassVar[str]
    sessions_dir_name: ClassVar[str]
    thread_name_prefix: ClassVar[str]
    tmux_session_prefix: ClassVar[str]
    error_cls: ClassVar[type[RuntimeSessionServiceError]] = RuntimeSessionServiceError
    read_model: ClassVar[type[Any]]
    chunk_model: ClassVar[type[Any]]
    events_response_model: ClassVar[type[Any]]

    def __init__(self) -> None:
        self.workspace_service = WorkspaceService()
        self.sessions_root = self.workspace_service.workspace_root.parent / self.sessions_dir_name
        self.sessions_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._sessions: dict[str, RuntimeSessionState] = {}

    def start_session(self, payload: Any) -> Any:
        """Start a new runtime subprocess for one prepared workspace."""
        with self._lock:
            existing = self._sessions.get(payload.run_id)
            if existing is not None:
                if existing.status == "running":
                    self._raise_error(
                        409,
                        f"{self.runtime_label} session is already running for this run.",
                    )
                self._raise_error(
                    409,
                    f"{self.runtime_label} session already exists for this run.",
                )

        workspace = self._get_workspace(payload.workspace_id)
        repo_path = Path(workspace.repo_path)
        self._validate_start_workspace(repo_path=repo_path, payload=payload)

        storage_dir = self._session_storage_dir(payload.run_id)
        storage_dir.mkdir(parents=True, exist_ok=True)
        self._reset_transport_files(storage_dir)
        launch = self._prepare_start_launch(repo_path=repo_path, payload=payload)
        use_tmux = self._tmux_available()
        process: subprocess.Popen[bytes] | None = None
        master_fd: int | None = None
        pid: int | None = None
        transport_kind = "tmux" if use_tmux else "pty"
        transport_ref: str | None = None

        if use_tmux:
            transport_ref = self._spawn_tmux_session(
                run_id=payload.run_id,
                launch=launch,
                repo_path=repo_path,
                storage_dir=storage_dir,
                stdin_payload=payload.prompt_text.encode("utf-8"),
            )
        else:
            process, master_fd = self._spawn_process(
                launch=launch,
                repo_path=repo_path,
                stdin_payload=payload.prompt_text.encode("utf-8"),
            )
            pid = process.pid
            transport_ref = str(process.pid)

        state = self._build_started_state(
            payload=payload,
            repo_path=repo_path,
            storage_dir=storage_dir,
            launch=launch,
            process=process,
            master_fd=master_fd,
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

    def resume_session(self, run_id: str) -> Any:
        """Resume an interrupted runtime session from persisted session state."""
        state = self._get_state(run_id)
        if state.status in {"running", "resuming"}:
            self._raise_error(
                409,
                f"{self.runtime_label} session is already active for this run.",
            )
        if state.status != "interrupted":
            self._raise_error(
                409,
                f"Only interrupted {self.runtime_label} sessions can be resumed.",
            )

        runtime_session_id = self._get_runtime_session_id(state)
        if not state.resumable or not runtime_session_id:
            self._raise_error(
                409,
                f"{self.runtime_label} session is not resumable for this run.",
            )
        if state.pid is not None and self._process_exists(state.pid):
            self._raise_error(
                409,
                f"Original {self.runtime_label} pid is still alive. "
                "Resume is blocked to avoid duplicate execution.",
            )

        repo_path = Path(state.repo_path)
        launch = self._prepare_resume_launch(state, repo_path, auto_resume=False)
        self._restart_session_from_launch(state, repo_path=repo_path, launch=launch)
        return self._to_read(state)

    def get_session(self, run_id: str) -> Any:
        """Return one existing session."""
        state = self._get_state(run_id)
        self._refresh_state(state)
        return self._to_read(state)

    def get_events(self, run_id: str, offset: int) -> Any:
        """Return terminal output chunks after the given offset."""
        state = self._get_state(run_id)
        self._refresh_state(state)
        items = [chunk for chunk in state.chunks if chunk.offset >= offset]
        return self.events_response_model(
            session=self._to_read(state),
            items=items,
            next_offset=len(state.chunks),
        )

    def cancel_session(self, run_id: str) -> Any:
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
                self._raise_error(
                    503,
                    f"Failed to cancel {self.runtime_label} session: {exc}",
                )
        return self._to_read(state)

    def _get_workspace(self, workspace_id: str) -> Any:
        """Return workspace metadata or normalize workspace errors."""
        try:
            return self.workspace_service.get_workspace(workspace_id)
        except WorkspaceServiceError as exc:
            raise self.error_cls(exc.status_code, exc.detail) from exc

    def _spawn_tmux_session(
        self,
        *,
        run_id: str,
        launch: RuntimeLaunchConfig,
        repo_path: Path,
        storage_dir: Path,
        stdin_payload: bytes | None,
    ) -> str:
        """Start one runtime command inside a detached tmux session."""
        session_name = self._tmux_session_name(run_id)
        self._kill_tmux_session(session_name, ignore_missing=True)

        stdin_path: Path | None = None
        if stdin_payload is not None:
            stdin_path = self._stdin_payload_path(storage_dir)
            stdin_path.write_bytes(stdin_payload)

        script_path = self._runner_script_path(storage_dir)
        script_path.write_text(
            self._build_tmux_runner_script(
                command=launch.command,
                script_exports=launch.script_exports,
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

    def _refresh_state(self, state: RuntimeSessionState) -> None:
        """Synchronize transport-backed session state before reading it."""
        if state.transport_kind == "tmux":
            self._refresh_tmux_state(state)

    def _refresh_tmux_state(self, state: RuntimeSessionState) -> None:
        """Update one tmux-backed session from persisted output and session liveness."""
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

    def _sync_tmux_output(self, state: RuntimeSessionState) -> None:
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
        chunk = self.chunk_model(
            offset=len(state.chunks),
            text=text,
            created_at=_utc_now(),
        )
        state.chunks.append(chunk)
        state.output_bytes_read += len(data)
        self._after_chunk_appended(state)
        self._persist_chunk(state, chunk)
        self._persist_state(state)

    def _finalize_tmux_state(self, state: RuntimeSessionState, *, exit_code: int) -> None:
        """Persist the final state of one finished tmux-backed session."""
        if state.finished_at is None:
            state.finished_at = _utc_now()
        self._apply_finished_state(state, exit_code=exit_code)
        self._persist_state(state)

    def _recover_lost_tmux_state(self, state: RuntimeSessionState) -> None:
        """Downgrade a tmux-backed session into an interrupted or failed state."""
        state.process = None
        state.master_fd = None
        state.recovered_from_restart = True
        state.finished_at = _utc_now()
        state.interrupted_at = state.finished_at

        if self._get_runtime_session_id(state):
            resumed = self._attempt_auto_semantic_resume(
                state,
                reason=(
                    f"tmux transport is no longer attached to the {self.runtime_label} session "
                    "after host executor recovery."
                ),
            )
            if resumed.status in {"running", "resuming"}:
                return
        else:
            state.status = "failed"
            state.resumable = False
            state.error_message = (
                f"tmux transport was lost and no resumable {self.runtime_label} session id "
                "was captured."
            )

        if state.summary_text is None:
            state.summary_text = self._derive_summary(state.chunks)
        self._persist_state(state)

    @staticmethod
    def _build_tmux_runner_script(
        *,
        command: list[str],
        script_exports: dict[str, str],
        stdin_path: Path | None,
        exit_code_path: Path,
    ) -> str:
        """Render the shell script executed inside the detached tmux session."""
        stdin_line = (
            f"cat {shlex.quote(str(stdin_path))} | {shlex.join(command)}"
            if stdin_path is not None
            else shlex.join(command)
        )
        lines = ["#!/bin/sh"]
        for key, value in sorted(script_exports.items()):
            lines.append(f"export {key}={shlex.quote(value)}")
        lines.extend(
            [
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
        return "\n".join(lines)

    def _start_background_threads(self, run_id: str) -> None:
        """Start reader and waiter threads for one active session."""
        reader_thread = threading.Thread(
            target=self._reader_loop,
            args=(run_id,),
            daemon=True,
            name=f"{self.thread_name_prefix}-reader-{run_id}",
        )
        waiter_thread = threading.Thread(
            target=self._wait_loop,
            args=(run_id,),
            daemon=True,
            name=f"{self.thread_name_prefix}-wait-{run_id}",
        )
        reader_thread.start()
        waiter_thread.start()

    def _spawn_process(
        self,
        *,
        launch: RuntimeLaunchConfig,
        repo_path: Path,
        stdin_payload: bytes | None,
    ) -> tuple[subprocess.Popen[bytes], int]:
        """Spawn a PTY-backed runtime subprocess and write the initial prompt."""
        master_fd, slave_fd = pty.openpty()
        env = os.environ.copy()
        env.update(launch.env_overrides)
        env.setdefault("TERM", "xterm-256color")
        env.setdefault("COLORTERM", "truecolor")
        env["CLICOLOR"] = "1"
        env["CLICOLOR_FORCE"] = "1"
        env["FORCE_COLOR"] = "1"
        env["PY_COLORS"] = "1"
        try:
            process = subprocess.Popen(
                launch.command,
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
            self._raise_error(503, f"{self.cli_label} is not installed on the host.")
        except OSError as exc:
            os.close(master_fd)
            os.close(slave_fd)
            self._raise_error(503, f"Failed to launch {self.cli_label}: {exc}")
        finally:
            os.close(slave_fd)

        try:
            if process.stdin is not None:
                if stdin_payload is not None:
                    process.stdin.write(stdin_payload)
                process.stdin.close()
        except OSError as exc:
            os.close(master_fd)
            self._raise_error(
                503,
                f"Failed to send prompt to {self.cli_label}: {exc}",
            )
        return process, master_fd

    @staticmethod
    def _tmux_available() -> bool:
        """Return whether tmux is available in PATH."""
        return shutil.which("tmux") is not None

    def _tmux_session_name(self, run_id: str) -> str:
        """Return a stable tmux session name for one run."""
        return f"{self.tmux_session_prefix}-{run_id}"

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
        """Return the shell wrapper path for one tmux-backed runtime run."""
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
            self._raise_error(503, "tmux is not installed on the host.")
        except OSError as exc:
            self._raise_error(503, f"Failed to launch tmux: {exc}")

        if result.returncode != 0:
            detail = "\n".join(
                chunk
                for chunk in (result.stdout.strip(), result.stderr.strip())
                if chunk
            )
            self._raise_error(503, detail or "tmux command failed.")
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
            self._raise_error(503, f"Failed to stop tmux session: {exc}")

        if result.returncode != 0 and not ignore_missing:
            detail = "\n".join(
                chunk
                for chunk in (result.stdout.strip(), result.stderr.strip())
                if chunk
            )
            self._raise_error(503, detail or "Failed to stop tmux session.")

    def _read_exit_code(self, state: RuntimeSessionState) -> int | None:
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
                chunk = self.chunk_model(
                    offset=len(state.chunks),
                    text=text,
                    created_at=_utc_now(),
                )
                state.chunks.append(chunk)
                self._after_chunk_appended(state)
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
            state.finished_at = _utc_now()
            self._apply_finished_state(state, exit_code=exit_code)
            self._persist_state(state)

    def _get_state(self, run_id: str) -> RuntimeSessionState:
        """Return mutable session state by run id or raise 404."""
        with self._lock:
            state = self._sessions.get(run_id)
            if state is not None:
                return state

        state = self._load_persisted_state(run_id)
        if state is None:
            self._raise_error(404, f"{self.runtime_label} session not found.")

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

    def _load_persisted_state(self, run_id: str) -> RuntimeSessionState | None:
        """Load a persisted session snapshot from disk and recover stale running states."""
        metadata_path = self._session_storage_dir(run_id) / "session.json"
        if not metadata_path.exists():
            return None

        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise self.error_cls(
                500,
                f"Persisted {self.runtime_label} session state is corrupted for run `{run_id}`.",
            ) from exc

        try:
            session = self.read_model.model_validate(payload)
        except Exception as exc:  # noqa: BLE001
            raise self.error_cls(
                500,
                f"Persisted {self.runtime_label} session state is invalid for run `{run_id}`.",
            ) from exc

        state = self._build_state_from_session(
            session=session,
            storage_dir=self._session_storage_dir(run_id),
            chunks=self._load_persisted_chunks(run_id),
        )

        if state.status in {"running", "resuming"}:
            if state.transport_kind == "tmux":
                return self._recover_tmux_running_state(state)
            return self._recover_interrupted_running_state(state)

        return state

    def _load_persisted_chunks(self, run_id: str) -> list[Any]:
        """Load persisted terminal chunks from disk."""
        chunks_path = self._session_storage_dir(run_id) / "chunks.jsonl"
        if not chunks_path.exists():
            return []

        items: list[Any] = []
        for raw_line in chunks_path.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip():
                continue
            try:
                payload = json.loads(raw_line)
                items.append(self.chunk_model.model_validate(payload))
            except Exception:  # noqa: BLE001
                continue
        return items

    def _recover_interrupted_running_state(
        self,
        state: RuntimeSessionState,
    ) -> RuntimeSessionState:
        """Reclassify a stale running PTY session after host executor restart."""
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
                f"Host executor restarted while the original {self.runtime_label} pid still "
                "appears alive. PTY reattach is not supported yet, so semantic resume is "
                "blocked to avoid duplicate execution."
            )
        elif self._get_runtime_session_id(state):
            return self._attempt_auto_semantic_resume(
                state,
                reason=(
                    f"Host executor restarted while {self.runtime_label} was running. "
                    "The live PTY session was interrupted."
                ),
            )
        else:
            state.status = "failed"
            state.resumable = False
            state.error_message = (
                f"Host executor restarted while {self.runtime_label} was running, "
                f"and no resumable {self.runtime_label} session id was captured."
            )

        if state.summary_text is None:
            state.summary_text = self._derive_summary(state.chunks)
        self._persist_state(state)
        return state

    def _recover_tmux_running_state(self, state: RuntimeSessionState) -> RuntimeSessionState:
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
        state: RuntimeSessionState,
        *,
        reason: str,
    ) -> RuntimeSessionState:
        """Try to auto-resume one interrupted session after host executor restart."""
        if not self._get_runtime_session_id(state):
            state.resumable = False
            state.error_message = f"{reason} No resumable {self.runtime_label} session id was captured."
            if state.summary_text is None:
                state.summary_text = self._derive_summary(state.chunks)
            self._persist_state(state)
            return state

        repo_path = Path(state.repo_path)
        try:
            launch = self._prepare_resume_launch(state, repo_path, auto_resume=True)
        except RuntimeSessionServiceError as exc:
            state.resumable = True
            state.error_message = f"{reason} {exc.detail}"
            if state.summary_text is None:
                state.summary_text = self._derive_summary(state.chunks)
            self._persist_state(state)
            return state

        self._reset_transport_files(Path(state.storage_dir), preserve_chunks=True)
        try:
            self._restart_session_from_launch(
                state,
                repo_path=repo_path,
                launch=launch,
                start_threads=False,
            )
        except RuntimeSessionServiceError as exc:
            state.resumable = True
            state.error_message = (
                f"{reason} Automatic semantic resume could not start: {exc.detail}"
            )
            if state.summary_text is None:
                state.summary_text = self._derive_summary(state.chunks)
            self._persist_state(state)
            return state

        state.error_message = (
            f"{reason} Automatic semantic resume started from the persisted "
            f"{self.runtime_label} session."
        )
        self._persist_state(state)
        return state

    def _persist_state(self, state: RuntimeSessionState) -> None:
        """Persist the latest public session snapshot to disk."""
        storage_dir = Path(state.storage_dir)
        storage_dir.mkdir(parents=True, exist_ok=True)
        (storage_dir / "session.json").write_text(
            json.dumps(self._to_read(state).model_dump(), ensure_ascii=True, indent=2),
            encoding="utf-8",
        )

    def _persist_chunk(self, state: RuntimeSessionState, chunk: Any) -> None:
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

    def _restart_session_from_launch(
        self,
        state: RuntimeSessionState,
        *,
        repo_path: Path,
        launch: RuntimeLaunchConfig,
        start_threads: bool = True,
    ) -> None:
        """Restart one interrupted session from a prepared launch config."""
        use_tmux = self._tmux_available()
        process: subprocess.Popen[bytes] | None = None
        master_fd: int | None = None
        pid: int | None = None
        transport_kind = "tmux" if use_tmux else "pty"
        transport_ref: str | None = None

        self._reset_transport_files(Path(state.storage_dir), preserve_chunks=True)
        if use_tmux:
            transport_ref = self._spawn_tmux_session(
                run_id=state.run_id,
                launch=launch,
                repo_path=repo_path,
                storage_dir=Path(state.storage_dir),
                stdin_payload=None,
            )
        else:
            process, master_fd = self._spawn_process(
                launch=launch,
                repo_path=repo_path,
                stdin_payload=None,
            )
            pid = process.pid
            transport_ref = str(process.pid)

        state.command = launch.command
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

        if start_threads and transport_kind == "pty":
            self._start_background_threads(state.run_id)

    def _apply_finished_state(self, state: RuntimeSessionState, *, exit_code: int) -> None:
        """Apply the terminal completion state shared by PTY and tmux transports."""
        state.exit_code = exit_code
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

    def _after_chunk_appended(self, state: RuntimeSessionState) -> None:
        """Apply shared post-processing after a terminal chunk is appended."""
        if state.status == "resuming":
            state.status = "running"

    def _raise_error(self, status_code: int, detail: str) -> None:
        """Raise the runtime-specific service error."""
        raise self.error_cls(status_code, detail)

    def _validate_start_workspace(self, *, repo_path: Path, payload: Any) -> None:
        raise NotImplementedError

    def _prepare_start_launch(self, *, repo_path: Path, payload: Any) -> RuntimeLaunchConfig:
        raise NotImplementedError

    def _prepare_resume_launch(
        self,
        state: RuntimeSessionState,
        repo_path: Path,
        *,
        auto_resume: bool,
    ) -> RuntimeLaunchConfig:
        raise NotImplementedError

    def _build_started_state(
        self,
        *,
        payload: Any,
        repo_path: Path,
        storage_dir: Path,
        launch: RuntimeLaunchConfig,
        process: subprocess.Popen[bytes] | None,
        master_fd: int | None,
        pid: int | None,
        transport_kind: str,
        transport_ref: str | None,
    ) -> RuntimeSessionState:
        raise NotImplementedError

    def _build_state_from_session(
        self,
        *,
        session: Any,
        storage_dir: Path,
        chunks: list[Any],
    ) -> RuntimeSessionState:
        raise NotImplementedError

    def _get_runtime_session_id(self, state: RuntimeSessionState) -> str | None:
        raise NotImplementedError

    def _to_read(self, state: RuntimeSessionState) -> Any:
        raise NotImplementedError

    @staticmethod
    def _derive_summary(chunks: list[Any]) -> str | None:
        raise NotImplementedError

    @staticmethod
    def _derive_error_message(chunks: list[Any], *, exit_code: int) -> str:
        raise NotImplementedError


def _utc_now() -> str:
    """Return a stable UTC timestamp."""
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
