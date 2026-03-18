"""Tests for workspace lifecycle proxy endpoints."""

from fastapi.testclient import TestClient

from app.api.v1 import workspaces
from app.schemas.workspace import (
    WorkspaceCommit,
    WorkspaceListResponse,
    WorkspaceMaterialize,
    WorkspacePrepare,
    WorkspacePullRequestCreate,
    WorkspaceRead,
)


def _auth_headers(client: TestClient) -> dict[str, str]:
    """Register the owner user and return bearer auth headers."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "owner@example.com",
            "password": "supersecure123",
            "display_name": "Owner",
        },
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_workspace_proxy_endpoints_return_normalized_payloads(
    client: TestClient,
    monkeypatch,
) -> None:
    """Workspace endpoints should expose normalized host-executor data."""
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
        workspaces.workspace_proxy_service,
        "list_workspaces",
        lambda: WorkspaceListResponse(items=[workspace], total=1),
    )
    monkeypatch.setattr(
        workspaces.workspace_proxy_service,
        "prepare_workspace",
        lambda payload: workspace,
    )
    monkeypatch.setattr(
        workspaces.workspace_proxy_service,
        "get_workspace",
        lambda workspace_id: workspace,
    )
    monkeypatch.setattr(
        workspaces.workspace_proxy_service,
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
        workspaces.workspace_proxy_service,
        "materialize_workspace",
        lambda workspace_id, payload: workspace.model_copy(
            update={
                "has_changes": True,
                "changed_files": [item["path"] for item in payload.model_dump()["files"]],
            }
        ),
    )
    monkeypatch.setattr(
        workspaces.workspace_proxy_service,
        "cleanup_workspace",
        lambda workspace_id: workspace.model_copy(
            update={
                "has_changes": False,
                "changed_files": [],
            }
        ),
    )
    monkeypatch.setattr(
        workspaces.workspace_proxy_service,
        "push_workspace",
        lambda workspace_id: workspace.model_copy(update={"status": "pushed"}),
    )
    monkeypatch.setattr(
        workspaces.workspace_proxy_service,
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
        workspaces.workspace_proxy_service,
        "delete_workspace",
        lambda workspace_id: None,
    )

    auth_headers = _auth_headers(client)

    list_response = client.get("/api/v1/workspaces", headers=auth_headers)
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["id"] == "ws-1"

    prepare_response = client.post(
        "/api/v1/workspaces/prepare",
        headers=auth_headers,
        json=WorkspacePrepare(owner="stemirkhan", repo="team-agent-platform").model_dump(),
    )
    assert prepare_response.status_code == 201
    assert prepare_response.json()["working_branch"] == "tap/team-agent-platform/demo-branch"

    get_response = client.get("/api/v1/workspaces/ws-1", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["changed_files"] == ["README.md"]

    commit_response = client.post(
        "/api/v1/workspaces/ws-1/commit",
        headers=auth_headers,
        json=WorkspaceCommit(message="test: commit workspace").model_dump(),
    )
    assert commit_response.status_code == 200
    assert commit_response.json()["status"] == "committed"
    assert commit_response.json()["last_commit_message"] == "test: commit workspace"

    materialize_response = client.post(
        "/api/v1/workspaces/ws-1/materialize",
        headers=auth_headers,
        json=WorkspaceMaterialize(
            files=[{"path": "TASK.md", "content": "# Task\n\nRun demo.\n"}]
        ).model_dump(),
    )
    assert materialize_response.status_code == 200
    assert materialize_response.json()["changed_files"] == ["TASK.md"]

    cleanup_response = client.post("/api/v1/workspaces/ws-1/cleanup", headers=auth_headers)
    assert cleanup_response.status_code == 200
    assert cleanup_response.json()["has_changes"] is False

    push_response = client.post("/api/v1/workspaces/ws-1/push", headers=auth_headers)
    assert push_response.status_code == 200
    assert push_response.json()["status"] == "pushed"

    pr_response = client.post(
        "/api/v1/workspaces/ws-1/pull-request",
        headers=auth_headers,
        json=WorkspacePullRequestCreate(title="Draft PR", body="Body").model_dump(),
    )
    assert pr_response.status_code == 200
    assert pr_response.json()["pull_request_number"] == 42

    delete_response = client.delete("/api/v1/workspaces/ws-1", headers=auth_headers)
    assert delete_response.status_code == 204
