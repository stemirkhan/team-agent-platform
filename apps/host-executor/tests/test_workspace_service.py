"""Service-level tests for host workspace file materialization cleanup."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

from host_executor_app.schemas.workspace import (
    WorkspaceCommandsRun,
    WorkspaceMaterialize,
    WorkspaceRead,
)
from host_executor_app.services import workspace_service as workspace_service_module
from host_executor_app.services.workspace_service import WorkspaceService


def _init_git_repo(repo_dir: Path) -> None:
    """Create a small committed git repository for workspace service tests."""
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)
    (repo_dir / "README.md").write_text("# Demo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "chore: init"], cwd=repo_dir, check=True)
    subprocess.run(["git", "checkout", "-b", "tap/demo"], cwd=repo_dir, check=True)


def test_cleanup_materialized_files_restores_original_repo_state(tmp_path, monkeypatch) -> None:
    """Temporary `.codex` scaffolding should not remain staged after cleanup."""
    monkeypatch.setattr(
        workspace_service_module,
        "get_settings",
        lambda: SimpleNamespace(workspace_root=str(tmp_path)),
    )
    service = WorkspaceService()

    workspace_dir = tmp_path / "ws-1"
    repo_dir = workspace_dir / "repo"
    repo_dir.mkdir(parents=True)
    _init_git_repo(repo_dir)

    existing_config = repo_dir / ".codex" / "config.toml"
    existing_config.parent.mkdir(parents=True, exist_ok=True)
    existing_config.write_text("[existing]\ntrusted = true\n", encoding="utf-8")
    subprocess.run(["git", "add", ".codex/config.toml"], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "chore: add codex config"], cwd=repo_dir, check=True)

    metadata = WorkspaceRead(
        id="ws-1",
        repo_owner="stemirkhan",
        repo_name="team-agent-platform",
        repo_full_name="stemirkhan/team-agent-platform",
        remote_url="https://github.com/stemirkhan/team-agent-platform.git",
        workspace_path=str(workspace_dir),
        repo_path=str(repo_dir),
        base_branch="main",
        working_branch="tap/demo",
        current_branch="tap/demo",
        status="prepared",
        created_at="2026-03-09T10:00:00Z",
        updated_at="2026-03-09T10:00:00Z",
    )
    service._save_workspace(metadata)

    materialized = service.materialize_workspace(
        "ws-1",
        WorkspaceMaterialize(
            files=[
                {
                    "path": ".codex/config.toml",
                    "content": "[features]\nmulti_agent = true\n",
                },
                {
                    "path": "TASK.md",
                    "content": "# Task\n\nRun Codex.\n",
                },
            ]
        ),
    )
    assert materialized.has_changes is True
    assert any(path.startswith(".codex") for path in materialized.changed_files)
    assert "TASK.md" in materialized.changed_files

    cleaned = service.cleanup_materialized_files("ws-1")
    assert cleaned.has_changes is False
    assert cleaned.changed_files == []
    assert existing_config.read_text(encoding="utf-8") == "[existing]\ntrusted = true\n"
    assert not (repo_dir / "TASK.md").exists()


def test_load_execution_config_reads_repo_contract(tmp_path, monkeypatch) -> None:
    """Repo-level TOML config should be normalized for one workspace."""
    monkeypatch.setattr(
        workspace_service_module,
        "get_settings",
        lambda: SimpleNamespace(workspace_root=str(tmp_path), workspace_command_timeout_seconds=30),
    )
    service = WorkspaceService()

    workspace_dir = tmp_path / "ws-config"
    repo_dir = workspace_dir / "repo"
    repo_dir.mkdir(parents=True)
    _init_git_repo(repo_dir)
    (repo_dir / ".team-agent-platform.toml").write_text(
        """
[run]
working_directory = "."

[setup]
commands = ["echo setup"]

[checks]
commands = ["echo check"]
""".strip(),
        encoding="utf-8",
    )

    metadata = WorkspaceRead(
        id="ws-config",
        repo_owner="stemirkhan",
        repo_name="team-agent-platform",
        repo_full_name="stemirkhan/team-agent-platform",
        remote_url="https://github.com/stemirkhan/team-agent-platform.git",
        workspace_path=str(workspace_dir),
        repo_path=str(repo_dir),
        base_branch="main",
        working_branch="tap/demo",
        current_branch="tap/demo",
        status="prepared",
        created_at="2026-03-09T10:00:00Z",
        updated_at="2026-03-09T10:00:00Z",
    )
    service._save_workspace(metadata)

    config = service.get_execution_config("ws-config")
    assert config.source_path == ".team-agent-platform.toml"
    assert config.setup_commands == ["echo setup"]
    assert config.check_commands == ["echo check"]


def test_run_commands_executes_shell_commands_in_workspace(tmp_path, monkeypatch) -> None:
    """Workspace commands should execute sequentially and return normalized output."""
    monkeypatch.setattr(
        workspace_service_module,
        "get_settings",
        lambda: SimpleNamespace(workspace_root=str(tmp_path), workspace_command_timeout_seconds=30),
    )
    service = WorkspaceService()

    workspace_dir = tmp_path / "ws-commands"
    repo_dir = workspace_dir / "repo"
    repo_dir.mkdir(parents=True)
    _init_git_repo(repo_dir)

    metadata = WorkspaceRead(
        id="ws-commands",
        repo_owner="stemirkhan",
        repo_name="team-agent-platform",
        repo_full_name="stemirkhan/team-agent-platform",
        remote_url="https://github.com/stemirkhan/team-agent-platform.git",
        workspace_path=str(workspace_dir),
        repo_path=str(repo_dir),
        base_branch="main",
        working_branch="tap/demo",
        current_branch="tap/demo",
        status="prepared",
        created_at="2026-03-09T10:00:00Z",
        updated_at="2026-03-09T10:00:00Z",
    )
    service._save_workspace(metadata)

    result = service.run_commands(
        "ws-commands",
        WorkspaceCommandsRun(
            commands=["printf 'hello world'"],
            working_directory=".",
            label="demo",
        ),
    )
    assert result.success is True
    assert result.items[0].output == "hello world"
