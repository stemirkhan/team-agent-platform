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


def test_cleanup_materialized_files_tolerates_missing_generated_file(tmp_path, monkeypatch) -> None:
    """Cleanup should not fail if Codex already removed one generated file."""
    monkeypatch.setattr(
        workspace_service_module,
        "get_settings",
        lambda: SimpleNamespace(workspace_root=str(tmp_path)),
    )
    service = WorkspaceService()

    workspace_dir = tmp_path / "ws-missing"
    repo_dir = workspace_dir / "repo"
    repo_dir.mkdir(parents=True)
    _init_git_repo(repo_dir)

    metadata = WorkspaceRead(
        id="ws-missing",
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

    service.materialize_workspace(
        "ws-missing",
        WorkspaceMaterialize(
            files=[
                {
                    "path": (
                        "agents/backend-platform-engineer/"
                        "playbooks/backend-platform-checklist.md"
                    ),
                    "content": "# Checklist\n",
                },
                {
                    "path": "TASK.md",
                    "content": "# Task\n",
                },
            ]
        ),
    )

    generated_skill = (
        repo_dir
        / "agents"
        / "backend-platform-engineer"
        / "playbooks"
        / "backend-platform-checklist.md"
    )
    generated_skill.unlink()

    cleaned = service.cleanup_materialized_files("ws-missing")
    assert cleaned.has_changes is False
    assert cleaned.changed_files == []
    assert not (repo_dir / "TASK.md").exists()


def test_get_workspace_inferrs_runtime_managed_commit_state(tmp_path, monkeypatch) -> None:
    """Refreshing workspace state should detect a direct runtime git commit."""
    monkeypatch.setattr(
        workspace_service_module,
        "get_settings",
        lambda: SimpleNamespace(workspace_root=str(tmp_path)),
    )
    service = WorkspaceService()

    workspace_dir = tmp_path / "ws-commit"
    repo_dir = workspace_dir / "repo"
    repo_dir.mkdir(parents=True)
    _init_git_repo(repo_dir)

    metadata = WorkspaceRead(
        id="ws-commit",
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
    baseline = service.get_workspace("ws-commit")

    (repo_dir / "README.md").write_text("# Demo\n\nRuntime change.\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo_dir, check=True)
    subprocess.run(
        ["git", "commit", "-m", "feat: runtime managed commit"],
        cwd=repo_dir,
        check=True,
    )

    refreshed = service.get_workspace("ws-commit")
    assert refreshed.status == "committed"
    assert refreshed.last_commit_sha != baseline.last_commit_sha
    assert refreshed.last_commit_message == "feat: runtime managed commit"
    assert refreshed.committed_at is not None


def test_get_workspace_keeps_uncommitted_runtime_changes_in_prepared_state(
    tmp_path,
    monkeypatch,
) -> None:
    """Refreshing workspace state should keep dirty files below the committed state."""
    monkeypatch.setattr(
        workspace_service_module,
        "get_settings",
        lambda: SimpleNamespace(workspace_root=str(tmp_path)),
    )
    service = WorkspaceService()

    workspace_dir = tmp_path / "ws-dirty"
    repo_dir = workspace_dir / "repo"
    repo_dir.mkdir(parents=True)
    _init_git_repo(repo_dir)

    metadata = WorkspaceRead(
        id="ws-dirty",
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

    baseline = service.get_workspace("ws-dirty")
    (repo_dir / "README.md").write_text("# Demo\n\nDirty runtime change.\n", encoding="utf-8")

    refreshed = service.get_workspace("ws-dirty")
    assert refreshed.status == "prepared"
    assert refreshed.has_changes is True
    assert refreshed.changed_files == ["README.md"]
    assert refreshed.initial_head_sha == baseline.last_commit_sha
    assert refreshed.last_commit_sha == baseline.last_commit_sha
    assert refreshed.committed_at is None


def test_get_workspace_inferrs_runtime_managed_push_and_pr(tmp_path, monkeypatch) -> None:
    """Refreshing workspace state should detect pushed branches and PRs created by runtime."""
    monkeypatch.setattr(
        workspace_service_module,
        "get_settings",
        lambda: SimpleNamespace(workspace_root=str(tmp_path)),
    )
    service = WorkspaceService()

    workspace_dir = tmp_path / "ws-pr"
    repo_dir = workspace_dir / "repo"
    repo_dir.mkdir(parents=True)
    _init_git_repo(repo_dir)

    metadata = WorkspaceRead(
        id="ws-pr",
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
    service.get_workspace("ws-pr")

    (repo_dir / "README.md").write_text("# Demo\n\nRuntime change.\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "feat: runtime managed pr"], cwd=repo_dir, check=True)
    commit_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    original_try_run_git = service._try_run_git
    monkeypatch.setattr(
        service,
        "_try_run_git",
        lambda args, *, cwd: (
            f"{commit_sha}\trefs/heads/tap/demo\n"
            if args == ["ls-remote", "--heads", "origin", "tap/demo"]
            else None
            if args == ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]
            else original_try_run_git(args, cwd=cwd)
        ),
    )
    monkeypatch.setattr(
        service,
        "_try_view_pull_by_reference",
        lambda repo_full_name, reference: {
            "number": 42,
            "url": "https://github.com/stemirkhan/team-agent-platform/pull/42",
        },
    )

    refreshed = service.get_workspace("ws-pr")
    assert refreshed.status == "pull_request_created"
    assert refreshed.upstream_branch == "origin/tap/demo"
    assert refreshed.pull_request_number == 42
    assert refreshed.pull_request_url == "https://github.com/stemirkhan/team-agent-platform/pull/42"
    assert refreshed.pushed_at is not None


def test_get_workspace_detects_runtime_managed_pr_without_local_tracking_ref(
    tmp_path,
    monkeypatch,
) -> None:
    """Refreshing workspace state should recover PR status from remote branch state alone."""
    monkeypatch.setattr(
        workspace_service_module,
        "get_settings",
        lambda: SimpleNamespace(workspace_root=str(tmp_path)),
    )
    service = WorkspaceService()

    workspace_dir = tmp_path / "ws-remote-pr"
    repo_dir = workspace_dir / "repo"
    repo_dir.mkdir(parents=True)
    _init_git_repo(repo_dir)

    metadata = WorkspaceRead(
        id="ws-remote-pr",
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
    service.get_workspace("ws-remote-pr")

    (repo_dir / "README.md").write_text("# Demo\n\nRuntime change.\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo_dir, check=True)
    subprocess.run(
        ["git", "commit", "-m", "feat: runtime managed remote pr"],
        cwd=repo_dir,
        check=True,
    )
    commit_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    original_try_run_git = service._try_run_git
    monkeypatch.setattr(
        service,
        "_try_run_git",
        lambda args, *, cwd: (
            f"{commit_sha}\trefs/heads/tap/demo\n"
            if args == ["ls-remote", "--heads", "origin", "tap/demo"]
            else None
            if args == ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]
            else original_try_run_git(args, cwd=cwd)
        ),
    )
    monkeypatch.setattr(
        service,
        "_try_view_pull_by_reference",
        lambda repo_full_name, reference: {
            "number": 42,
            "url": "https://github.com/stemirkhan/team-agent-platform/pull/42",
        },
    )

    refreshed = service.get_workspace("ws-remote-pr")
    assert refreshed.status == "pull_request_created"
    assert refreshed.upstream_branch == "origin/tap/demo"
    assert refreshed.pull_request_number == 42
    assert refreshed.pull_request_url == "https://github.com/stemirkhan/team-agent-platform/pull/42"
    assert refreshed.pushed_at is not None


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
