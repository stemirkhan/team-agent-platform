"""Service-level tests for persisted Codex session recovery."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from host_executor_app.schemas.codex import CodexSessionStart, CodexTerminalChunk
from host_executor_app.services import workspace_service as workspace_service_module
from host_executor_app.services.codex_session_service import CodexSessionService


def test_get_session_recovers_persisted_running_session_as_failed(tmp_path, monkeypatch) -> None:
    """A persisted running session should not remain stuck after host executor restart."""
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
    assert session.status == "failed"
    assert "host executor restarted" in (session.error_message or "").lower()
    assert session.finished_at is not None

    events = service.get_events("run-1", offset=0)
    assert len(events.items) == 1
    assert events.items[0].text == '{"type":"turn.started"}\n'


def test_build_command_enables_colorized_terminal_output(tmp_path, monkeypatch) -> None:
    """Codex sessions should keep ANSI colors enabled for the live terminal."""
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
