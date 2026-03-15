"""Smoke tests for host executor workspace lifecycle endpoints."""

from fastapi.testclient import TestClient

from host_executor_app.api import workspaces as workspace_api
from host_executor_app.main import app
from host_executor_app.schemas.workspace import (
    WorkspaceCommandResult,
    WorkspaceCommandsRun,
    WorkspaceCommandsRunResponse,
    WorkspaceCommit,
    WorkspaceListResponse,
    WorkspaceMaterialize,
    WorkspacePrepare,
    WorkspacePullRequestCreate,
    WorkspaceRead,
)


def test_host_executor_workspace_endpoints(monkeypatch) -> None:
    """Workspace lifecycle endpoints should expose normalized payloads."""
    client = TestClient(app)

    workspace = WorkspaceRead(
        id="ws-1",
        repo_owner="stemirkhan",
        repo_name="team-agent-platform",
        repo_full_name="stemirkhan/team-agent-platform",
        remote_url="https://github.com/stemirkhan/team-agent-platform.git",
        workspace_path="/tmp/ws-1",
        repo_path="/tmp/ws-1/repo",
        base_branch="main",
        working_branch="tap/team-agent-platform/demo-branch",
        current_branch="tap/team-agent-platform/demo-branch",
        upstream_branch="origin/tap/team-agent-platform/demo-branch",
        status="prepared",
        has_changes=True,
        changed_files=["README.md"],
        last_commit_sha="abc123",
        created_at="2026-03-08T10:00:00Z",
        updated_at="2026-03-08T10:05:00Z",
    )

    monkeypatch.setattr(
        workspace_api.workspace_service,
        "list_workspaces",
        lambda: WorkspaceListResponse(items=[workspace], total=1),
    )
    monkeypatch.setattr(
        workspace_api.workspace_service,
        "prepare_workspace",
        lambda payload: workspace,
    )
    monkeypatch.setattr(
        workspace_api.workspace_service,
        "get_workspace",
        lambda workspace_id: workspace,
    )
    monkeypatch.setattr(
        workspace_api.workspace_service,
        "commit_workspace",
        lambda workspace_id, payload: workspace.model_copy(
            update={
                "status": "committed",
                "has_changes": False,
                "changed_files": [],
                "last_commit_message": payload.message,
            }
        ),
    )
    monkeypatch.setattr(
        workspace_api.workspace_service,
        "materialize_workspace",
        lambda workspace_id, payload: workspace.model_copy(
            update={
                "has_changes": True,
                "changed_files": [item["path"] for item in payload.model_dump()["files"]],
            }
        ),
    )
    monkeypatch.setattr(
        workspace_api.workspace_service,
        "cleanup_materialized_files",
        lambda workspace_id: workspace.model_copy(
            update={
                "has_changes": False,
                "changed_files": [],
            }
        ),
    )
    monkeypatch.setattr(
        workspace_api.workspace_service,
        "run_commands",
        lambda workspace_id, payload: WorkspaceCommandsRunResponse(
            label=payload.label,
            working_directory=payload.working_directory,
            success=True,
            items=[
                WorkspaceCommandResult(
                    command=payload.commands[0],
                    exit_code=0,
                    output="ok",
                    started_at="2026-03-09T10:00:00Z",
                    finished_at="2026-03-09T10:00:01Z",
                    succeeded=True,
                )
            ],
        ),
    )
    monkeypatch.setattr(
        workspace_api.workspace_service,
        "push_workspace",
        lambda workspace_id: workspace.model_copy(update={"status": "pushed"}),
    )
    monkeypatch.setattr(
        workspace_api.workspace_service,
        "create_pull_request",
        lambda workspace_id, payload: workspace.model_copy(
            update={
                "status": "pull_request_created",
                "pull_request_number": 42,
                "pull_request_url": "https://github.com/stemirkhan/team-agent-platform/pull/42",
            }
        ),
    )
    monkeypatch.setattr(
        workspace_api.workspace_service,
        "delete_workspace",
        lambda workspace_id: None,
    )

    list_response = client.get("/workspaces")
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["id"] == "ws-1"

    prepare_response = client.post(
        "/workspaces/prepare",
        json=WorkspacePrepare(owner="stemirkhan", repo="team-agent-platform").model_dump(),
    )
    assert prepare_response.status_code == 201
    assert prepare_response.json()["working_branch"] == "tap/team-agent-platform/demo-branch"

    get_response = client.get("/workspaces/ws-1")
    assert get_response.status_code == 200
    assert get_response.json()["changed_files"] == ["README.md"]

    commit_response = client.post(
        "/workspaces/ws-1/commit",
        json=WorkspaceCommit(message="test: commit workspace").model_dump(),
    )
    assert commit_response.status_code == 200
    assert commit_response.json()["status"] == "committed"
    assert commit_response.json()["last_commit_message"] == "test: commit workspace"

    materialize_response = client.post(
        "/workspaces/ws-1/materialize",
        json=WorkspaceMaterialize(
            files=[{"path": ".codex/config.toml", "content": "[features]\nmulti_agent = true\n"}]
        ).model_dump(),
    )
    assert materialize_response.status_code == 200
    assert materialize_response.json()["changed_files"] == [".codex/config.toml"]

    cleanup_response = client.post("/workspaces/ws-1/cleanup")
    assert cleanup_response.status_code == 200
    assert cleanup_response.json()["has_changes"] is False

    commands_response = client.post(
        "/workspaces/ws-1/commands",
        json=WorkspaceCommandsRun(
            commands=["make compose-config"],
            working_directory=".",
            label="repo-checks",
        ).model_dump(),
    )
    assert commands_response.status_code == 200
    assert commands_response.json()["success"] is True

    push_response = client.post("/workspaces/ws-1/push")
    assert push_response.status_code == 200
    assert push_response.json()["status"] == "pushed"

    pr_response = client.post(
        "/workspaces/ws-1/pull-request",
        json=WorkspacePullRequestCreate(title="Draft PR", body="Body").model_dump(),
    )
    assert pr_response.status_code == 200
    assert pr_response.json()["pull_request_number"] == 42

    delete_response = client.delete("/workspaces/ws-1")
    assert delete_response.status_code == 204
