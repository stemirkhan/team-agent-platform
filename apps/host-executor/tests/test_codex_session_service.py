"""Service-level tests for persisted Codex session recovery."""

from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from host_executor_app.schemas.codex import CodexSessionStart, CodexTerminalChunk
from host_executor_app.services import workspace_service as workspace_service_module
from host_executor_app.services.codex_session_service import CodexSessionService, _SessionState


def test_get_session_recovers_persisted_running_session_as_interrupted(
    tmp_path,
    monkeypatch,
) -> None:
    """A persisted running session should become resumable after host executor restart."""
    monkeypatch.setattr(
        workspace_service_module,
        "get_settings",
        lambda: SimpleNamespace(workspace_root=str(tmp_path / "workspaces")),
    )
    service = CodexSessionService()

    storage_dir = service.sessions_root / "run-1"
    storage_dir.mkdir(parents=True, exist_ok=True)
    (storage_dir / "session.json").write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "workspace_id": "ws-1",
                "repo_path": "/tmp/ws-1/repo",
                "command": ["codex", "exec", "--json"],
                "status": "running",
                "pid": 999999,
                "exit_code": None,
                "error_message": None,
                "summary_text": None,
                "codex_session_id": "019cdddb-4df9-7100-ae82-b8b061ad6cbb",
                "transport_kind": "pty",
                "transport_ref": "999999",
                "resume_attempt_count": 0,
                "interrupted_at": None,
                "resumable": False,
                "recovered_from_restart": False,
                "started_at": "2026-03-09T10:00:00Z",
                "finished_at": None,
                "last_output_offset": 1,
            },
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )
    with (storage_dir / "chunks.jsonl").open("w", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                CodexTerminalChunk(
                    offset=0,
                    text='{"type":"turn.started"}\n',
                    created_at="2026-03-09T10:00:01Z",
                ).model_dump(),
                ensure_ascii=True,
            )
        )
        handle.write("\n")

    session = service.get_session("run-1")
    assert session.status == "interrupted"
    assert session.resumable is True
    assert session.codex_session_id == "019cdddb-4df9-7100-ae82-b8b061ad6cbb"
    assert "host executor restarted" in (session.error_message or "").lower()
    assert session.finished_at is not None

    events = service.get_events("run-1", offset=0)
    assert len(events.items) == 1
    assert events.items[0].text == '{"type":"turn.started"}\n'


def test_get_session_auto_resumes_persisted_running_session_after_restart(
    tmp_path,
    monkeypatch,
) -> None:
    """A recoverable PTY session should auto-resume after host executor restart."""
    monkeypatch.setattr(
        workspace_service_module,
        "get_settings",
        lambda: SimpleNamespace(workspace_root=str(tmp_path / "workspaces")),
    )
    service = CodexSessionService()

    repo_path = tmp_path / "workspaces" / "ws-auto" / "repo"
    repo_path.mkdir(parents=True, exist_ok=True)
    codex_home = repo_path.parent / "codex-home"
    codex_home.mkdir(parents=True, exist_ok=True)

    storage_dir = service.sessions_root / "run-auto"
    storage_dir.mkdir(parents=True, exist_ok=True)
    (storage_dir / "session.json").write_text(
        json.dumps(
            {
                "run_id": "run-auto",
                "workspace_id": "ws-auto",
                "repo_path": str(repo_path),
                "command": ["codex", "exec", "--json"],
                "status": "running",
                "pid": 999999,
                "exit_code": None,
                "error_message": None,
                "summary_text": None,
                "codex_session_id": "019cdddb-4df9-7100-ae82-b8b061ad6cbb",
                "transport_kind": "pty",
                "transport_ref": "999999",
                "resume_attempt_count": 0,
                "interrupted_at": None,
                "resumable": False,
                "recovered_from_restart": False,
                "started_at": "2026-03-09T10:00:00Z",
                "finished_at": None,
                "last_output_offset": 0,
            },
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )

    class _FakeProcess:
        pid = 43210

        @staticmethod
        def poll():
            return None

    started_threads: list[str] = []
    monkeypatch.setattr(service, "_tmux_available", lambda: False)
    monkeypatch.setattr(service, "_process_exists", lambda pid: False)
    monkeypatch.setattr(
        service,
        "_start_background_threads",
        lambda run_id: started_threads.append(run_id),
    )
    monkeypatch.setattr(service, "_spawn_process", lambda **kwargs: (_FakeProcess(), 77))

    session = service.get_session("run-auto")
    assert session.status == "resuming"
    assert session.resume_attempt_count == 1
    assert session.resumable is False
    assert session.pid == 43210
    assert session.transport_ref == "43210"
    assert started_threads == ["run-auto"]
    assert "automatic semantic resume started" in (session.error_message or "").lower()

    persisted = json.loads((storage_dir / "session.json").read_text(encoding="utf-8"))
    assert persisted["status"] == "resuming"
    assert persisted["resume_attempt_count"] == 1


def test_build_command_enables_colorized_terminal_output(tmp_path, monkeypatch) -> None:
    """Codex sessions should keep ANSI colors and multi-agent enabled."""
    monkeypatch.setattr(
        workspace_service_module,
        "get_settings",
        lambda: SimpleNamespace(workspace_root=str(tmp_path / "workspaces")),
    )
    service = CodexSessionService()

    command = service._build_command(
        repo_path=Path("/tmp/repo"),
        payload=CodexSessionStart(
            run_id="run-color",
            workspace_id="ws-color",
            prompt_text="Run a color smoke test.",
        ),
    )

    color_index = command.index("--color")
    assert command[color_index + 1] == "always"
    enable_index = command.index("--enable")
    assert command[enable_index + 1] == "multi_agent"
    assert "--ephemeral" not in command


def test_build_resume_command_enables_multi_agent() -> None:
    """Resume commands should keep multi-agent enabled explicitly."""
    command = CodexSessionService._build_resume_command(
        "019cdddb-4df9-7100-ae82-b8b061ad6cbb"
    )

    enable_index = command.index("--enable")
    assert command[enable_index + 1] == "multi_agent"


def test_derive_summary_uses_agent_message_before_turn_completed() -> None:
    """Structured turn completion should reuse the last agent message as a safe summary."""
    chunks = [
        CodexTerminalChunk(
            offset=0,
            text='{"type":"thread.started","thread_id":"019cdddb-4df9-7100-ae82-b8b061ad6cbb"}\n'
            '{"type":"turn.started"}\n',
            created_at="2026-03-09T10:00:00Z",
        ),
        CodexTerminalChunk(
            offset=1,
            text=(
                '{"type":"item.completed","item":{"id":"item_0","type":"agent_message",'
                '"text":"Implemented the execution board fix and validated the main checks."}}\n'
                '{"type":"turn.completed","usage":{"input_tokens":123,"output_tokens":45}}\n'
            ),
            created_at="2026-03-09T10:05:00Z",
        ),
    ]

    assert (
        CodexSessionService._derive_summary(chunks)
        == "Implemented the execution board fix and validated the main checks."
    )


def test_derive_summary_ignores_raw_command_output_without_turn_completed() -> None:
    """Raw terminal tails should not become summary text when no turn completed event exists."""
    chunks = [
        CodexTerminalChunk(
            offset=0,
            text='{"type":"turn.started"}\n',
            created_at="2026-03-09T10:00:00Z",
        ),
        CodexTerminalChunk(
            offset=1,
            text=(
                'const summary = "<div className=\\"rounded-2xl\\">";\n'
                '{"type":"item.completed","item":{"id":"item_1","type":"command_execution",'
                '"command":"cat component.tsx","aggregated_output":"<div>raw jsx</div>",'
                '"exit_code":0,"status":"completed"}}\n'
            ),
            created_at="2026-03-09T10:05:00Z",
        ),
    ]

    assert CodexSessionService._derive_summary(chunks) is None


def test_get_session_exposes_latest_token_usage(tmp_path, monkeypatch) -> None:
    """Persisted session metadata should expose the latest token usage from terminal chunks."""
    monkeypatch.setattr(
        workspace_service_module,
        "get_settings",
        lambda: SimpleNamespace(workspace_root=str(tmp_path / "workspaces")),
    )
    service = CodexSessionService()

    storage_dir = service.sessions_root / "run-usage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    (storage_dir / "session.json").write_text(
        json.dumps(
            {
                "run_id": "run-usage",
                "workspace_id": "ws-usage",
                "repo_path": "/tmp/ws-usage/repo",
                "command": ["codex", "exec", "--json"],
                "status": "completed",
                "pid": 101,
                "exit_code": 0,
                "error_message": None,
                "summary_text": "done",
                "codex_session_id": None,
                "transport_kind": "pty",
                "transport_ref": "101",
                "resume_attempt_count": 0,
                "interrupted_at": None,
                "resumable": False,
                "recovered_from_restart": False,
                "started_at": "2026-03-09T10:00:00Z",
                "finished_at": "2026-03-09T10:05:00Z",
                "last_output_offset": 1,
            },
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )
    with (storage_dir / "chunks.jsonl").open("w", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                CodexTerminalChunk(
                    offset=0,
                    text='{"type":"turn.completed","usage":{"input_tokens":3417189,"output_tokens":23804}}\n',
                    created_at="2026-03-09T10:05:00Z",
                ).model_dump(),
                ensure_ascii=True,
            )
        )
        handle.write("\n")

    session = service.get_session("run-usage")
    assert session.input_tokens == 3417189
    assert session.output_tokens == 23804


def test_resume_session_restarts_interrupted_session(tmp_path, monkeypatch) -> None:
    """Interrupted sessions should restart through `codex exec resume`."""
    monkeypatch.setattr(
        workspace_service_module,
        "get_settings",
        lambda: SimpleNamespace(workspace_root=str(tmp_path / "workspaces")),
    )
    service = CodexSessionService()

    repo_path = tmp_path / "workspaces" / "ws-1" / "repo"
    repo_path.mkdir(parents=True, exist_ok=True)
    codex_home = repo_path.parent / "codex-home"
    codex_home.mkdir(parents=True, exist_ok=True)

    storage_dir = service.sessions_root / "run-resume"
    storage_dir.mkdir(parents=True, exist_ok=True)
    (storage_dir / "session.json").write_text(
        json.dumps(
            {
                "run_id": "run-resume",
                "workspace_id": "ws-1",
                "repo_path": str(repo_path),
                "command": ["codex", "exec", "--json"],
                "status": "interrupted",
                "pid": 101,
                "exit_code": None,
                "error_message": "Host executor restarted.",
                "summary_text": "working",
                "codex_session_id": "019cdddb-4df9-7100-ae82-b8b061ad6cbb",
                "transport_kind": "pty",
                "transport_ref": "101",
                "resume_attempt_count": 1,
                "interrupted_at": "2026-03-09T10:04:00Z",
                "resumable": True,
                "recovered_from_restart": True,
                "started_at": "2026-03-09T10:00:00Z",
                "finished_at": "2026-03-09T10:04:00Z",
                "last_output_offset": 1,
            },
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )
    (storage_dir / "chunks.jsonl").write_text("", encoding="utf-8")

    class _FakeProcess:
        pid = 43210

        @staticmethod
        def poll():
            return None

    monkeypatch.setattr(service, "_tmux_available", lambda: False)
    monkeypatch.setattr(service, "_start_background_threads", lambda run_id: None)
    monkeypatch.setattr(service, "_process_exists", lambda pid: False)
    monkeypatch.setattr(
        service,
        "_spawn_process",
        lambda **kwargs: (_FakeProcess(), 77),
    )

    session = service.resume_session("run-resume")
    assert session.status == "resuming"
    assert session.resume_attempt_count == 2
    assert session.pid == 43210
    assert session.transport_ref == "43210"

    persisted = json.loads((storage_dir / "session.json").read_text(encoding="utf-8"))
    assert persisted["status"] == "resuming"
    assert persisted["resume_attempt_count"] == 2
    assert persisted["resumable"] is False


def test_reader_loop_extracts_codex_session_id(tmp_path, monkeypatch) -> None:
    """The reader loop should persist the Codex thread id from JSONL terminal output."""
    monkeypatch.setattr(
        workspace_service_module,
        "get_settings",
        lambda: SimpleNamespace(workspace_root=str(tmp_path / "workspaces")),
    )
    service = CodexSessionService()
    storage_dir = service.sessions_root / "run-reader"
    storage_dir.mkdir(parents=True, exist_ok=True)

    service._sessions["run-reader"] = _SessionState(
        run_id="run-reader",
        workspace_id="ws-reader",
        repo_path="/tmp/ws-reader/repo",
        command=["codex", "exec", "--json"],
        started_at="2026-03-09T10:00:00Z",
        storage_dir=str(storage_dir),
        master_fd=11,
        pid=123,
    )

    output = io.BytesIO(
        b'{"type":"thread.started","thread_id":"019cdddb-4df9-7100-ae82-b8b061ad6cbb"}\n'
    )

    def _fake_read(fd: int, size: int) -> bytes:
        return output.read(size)

    with patch("os.read", side_effect=_fake_read), patch("os.close"):
        service._reader_loop("run-reader")

    session = service.get_session("run-reader")
    assert session.codex_session_id == "019cdddb-4df9-7100-ae82-b8b061ad6cbb"


def test_get_session_reattaches_running_tmux_session_after_restart(tmp_path, monkeypatch) -> None:
    """tmux-backed sessions should remain running after host executor restart."""
    monkeypatch.setattr(
        workspace_service_module,
        "get_settings",
        lambda: SimpleNamespace(workspace_root=str(tmp_path / "workspaces")),
    )
    service = CodexSessionService()
    storage_dir = service.sessions_root / "run-tmux"
    storage_dir.mkdir(parents=True, exist_ok=True)
    raw_output_path = storage_dir / "pane.log"
    raw_output_path.write_bytes(
        b'{"type":"thread.started","thread_id":"019cdddb-4df9-7100-ae82-b8b061ad6cbb"}\n'
    )
    (storage_dir / "session.json").write_text(
        json.dumps(
            {
                "run_id": "run-tmux",
                "workspace_id": "ws-tmux",
                "repo_path": "/tmp/ws-tmux/repo",
                "command": ["codex", "exec", "--json"],
                "status": "running",
                "pid": None,
                "exit_code": None,
                "error_message": None,
                "summary_text": None,
                "codex_session_id": None,
                "transport_kind": "tmux",
                "transport_ref": "tap-run-run-tmux",
                "resume_attempt_count": 0,
                "interrupted_at": None,
                "resumable": False,
                "recovered_from_restart": False,
                "output_bytes_read": 0,
                "started_at": "2026-03-09T10:00:00Z",
                "finished_at": None,
                "last_output_offset": 0,
            },
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(service, "_tmux_session_exists", lambda session_name: True)

    session = service.get_session("run-tmux")
    assert session.status == "running"
    assert session.transport_kind == "tmux"
    assert session.recovered_from_restart is True
    assert session.codex_session_id == "019cdddb-4df9-7100-ae82-b8b061ad6cbb"
    assert session.last_output_offset == 1


def test_get_session_marks_tmux_session_interrupted_when_transport_disappears(
    tmp_path,
    monkeypatch,
) -> None:
    """tmux session loss should auto-resume from the persisted Codex session id."""
    monkeypatch.setattr(
        workspace_service_module,
        "get_settings",
        lambda: SimpleNamespace(workspace_root=str(tmp_path / "workspaces")),
    )
    service = CodexSessionService()
    repo_path = tmp_path / "ws-tmux-lost" / "repo"
    repo_path.mkdir(parents=True, exist_ok=True)
    codex_home = repo_path.parent / "codex-home"
    codex_home.mkdir(parents=True, exist_ok=True)
    storage_dir = service.sessions_root / "run-tmux-lost"
    storage_dir.mkdir(parents=True, exist_ok=True)
    (storage_dir / "session.json").write_text(
        json.dumps(
            {
                "run_id": "run-tmux-lost",
                "workspace_id": "ws-tmux-lost",
                "repo_path": str(repo_path),
                "command": ["codex", "exec", "--json"],
                "status": "running",
                "pid": None,
                "exit_code": None,
                "error_message": None,
                "summary_text": None,
                "codex_session_id": "019cdddb-4df9-7100-ae82-b8b061ad6cbb",
                "transport_kind": "tmux",
                "transport_ref": "tap-run-run-tmux-lost",
                "resume_attempt_count": 0,
                "interrupted_at": None,
                "resumable": False,
                "recovered_from_restart": False,
                "output_bytes_read": 0,
                "started_at": "2026-03-09T10:00:00Z",
                "finished_at": None,
                "last_output_offset": 0,
            },
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )
    def _tmux_session_exists(session_name: str) -> bool:
        return session_name == "tap-run-run-tmux-lost-resumed"

    monkeypatch.setattr(service, "_tmux_session_exists", _tmux_session_exists)
    monkeypatch.setattr(service, "_tmux_available", lambda: True)
    monkeypatch.setattr(
        service,
        "_spawn_tmux_session",
        lambda **kwargs: "tap-run-run-tmux-lost-resumed",
    )

    session = service.get_session("run-tmux-lost")
    assert session.status == "running"
    assert session.resumable is False
    assert session.transport_kind == "tmux"
    assert session.transport_ref == "tap-run-run-tmux-lost-resumed"
    assert session.resume_attempt_count == 1
    assert session.error_message is None
