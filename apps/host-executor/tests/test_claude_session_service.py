"""Service-level tests for persisted Claude session recovery."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from types import SimpleNamespace

from host_executor_app.schemas.claude import ClaudeSessionStart, ClaudeTerminalChunk
from host_executor_app.services import workspace_service as workspace_service_module
from host_executor_app.services.claude_session_service import ClaudeSessionService


def test_build_command_uses_stream_json_and_deterministic_session_id(
    tmp_path,
    monkeypatch,
) -> None:
    """Claude sessions should use stream-json with a stable per-run session id."""
    monkeypatch.setattr(
        workspace_service_module,
        "get_settings",
        lambda: SimpleNamespace(workspace_root=str(tmp_path / "workspaces")),
    )
    service = ClaudeSessionService()

    session_id = service._session_id_for_run("run-claude-color")
    command = service._build_command(
        payload=ClaudeSessionStart(
            run_id="run-claude-color",
            workspace_id="ws-claude-color",
            prompt_text="Run a Claude color smoke test.",
            model="sonnet",
            effort="high",
            permission_mode="bypassPermissions",
        ),
        session_id=session_id,
    )

    assert command[:5] == ["claude", "-p", "--verbose", "--output-format", "stream-json"]
    permission_index = command.index("--permission-mode")
    assert command[permission_index + 1] == "bypassPermissions"
    session_index = command.index("--session-id")
    assert command[session_index + 1] == session_id
    model_index = command.index("--model")
    assert command[model_index + 1] == "sonnet"
    effort_index = command.index("--effort")
    assert command[effort_index + 1] == "high"


def test_build_resume_command_uses_resume_flag() -> None:
    """Resume commands should preserve stream-json and the persisted session id."""
    command = ClaudeSessionService._build_resume_command(
        "88a7b103-6ca7-52f1-a774-a713ca889ed8"
    )

    assert command[:5] == ["claude", "-p", "--verbose", "--output-format", "stream-json"]
    permission_index = command.index("--permission-mode")
    assert command[permission_index + 1] == "bypassPermissions"
    resume_index = command.index("--resume")
    assert command[resume_index + 1] == "88a7b103-6ca7-52f1-a774-a713ca889ed8"


def test_session_id_for_run_is_deterministic_for_non_uuid() -> None:
    """Run ids should map to a stable UUID even when they are not UUID-shaped."""
    first = ClaudeSessionService._session_id_for_run("delivery-run-42")
    second = ClaudeSessionService._session_id_for_run("delivery-run-42")
    third = ClaudeSessionService._session_id_for_run("delivery-run-43")

    assert first == second
    assert first != third
    assert str(uuid.UUID(first)) == first


def test_get_session_auto_resumes_persisted_running_session_after_restart(
    tmp_path,
    monkeypatch,
) -> None:
    """A recoverable Claude PTY session should auto-resume after host executor restart."""
    monkeypatch.setattr(
        workspace_service_module,
        "get_settings",
        lambda: SimpleNamespace(workspace_root=str(tmp_path / "workspaces")),
    )
    service = ClaudeSessionService()

    repo_path = tmp_path / "workspaces" / "ws-auto" / "repo"
    repo_path.mkdir(parents=True, exist_ok=True)

    storage_dir = service.sessions_root / "run-auto"
    storage_dir.mkdir(parents=True, exist_ok=True)
    (storage_dir / "session.json").write_text(
        json.dumps(
            {
                "run_id": "run-auto",
                "workspace_id": "ws-auto",
                "repo_path": str(repo_path),
                "command": [
                    "claude",
                    "-p",
                    "--verbose",
                    "--output-format",
                    "stream-json",
                ],
                "status": "running",
                "pid": 999999,
                "exit_code": None,
                "error_message": None,
                "summary_text": None,
                "claude_session_id": "88a7b103-6ca7-52f1-a774-a713ca889ed8",
                "transport_kind": "pty",
                "transport_ref": "999999",
                "resume_attempt_count": 0,
                "interrupted_at": None,
                "resumable": False,
                "recovered_from_restart": False,
                "started_at": "2026-03-14T10:00:00Z",
                "finished_at": None,
                "last_output_offset": 0,
            },
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )
    with (storage_dir / "chunks.jsonl").open("w", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                ClaudeTerminalChunk(
                    offset=0,
                    text='{"type":"system","subtype":"init"}\n',
                    created_at="2026-03-14T10:00:01Z",
                ).model_dump(),
                ensure_ascii=True,
            )
        )
        handle.write("\n")

    class _FakeProcess:
        pid = 54321

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
    assert session.pid == 54321
    assert session.transport_ref == "54321"
    assert session.claude_session_id == "88a7b103-6ca7-52f1-a774-a713ca889ed8"
    assert started_threads == ["run-auto"]
    assert "automatic semantic resume started" in (session.error_message or "").lower()

    persisted = json.loads((storage_dir / "session.json").read_text(encoding="utf-8"))
    assert persisted["status"] == "resuming"
    assert persisted["resume_attempt_count"] == 1
