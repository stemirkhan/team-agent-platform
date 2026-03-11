"""Integration tests for run preparation endpoints."""

from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient

from app.schemas.codex import CodexSessionEventsResponse, CodexSessionRead, CodexTerminalChunk
from app.schemas.github import GitHubIssueDetailRead, GitHubRepoRead
from app.schemas.workspace import (
    WorkspaceCommandResult,
    WorkspaceCommandsRunResponse,
    WorkspaceExecutionConfigRead,
    WorkspaceRead,
)
from app.services.codex_proxy_service import CodexProxyService, CodexProxyServiceError
from app.services.export_service import ExportService
from app.services.github_proxy_service import GitHubProxyService
from app.services.host_execution_service import HostExecutionReadinessService
from app.services.workspace_proxy_service import WorkspaceProxyService, WorkspaceProxyServiceError


def _auth_headers(client: TestClient, *, email: str, display_name: str) -> dict[str, str]:
    """Register user and return bearer auth headers."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "supersecure123",
            "display_name": display_name,
        },
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _publish_agent(client: TestClient, *, headers: dict[str, str], slug: str, title: str) -> None:
    """Create and publish one minimal agent profile."""
    create_response = client.post(
        "/api/v1/agents",
        headers=headers,
        json={
            "slug": slug,
            "title": title,
            "short_description": f"{title} short description.",
            "full_description": f"{title} full description.",
            "category": "backend",
        },
    )
    assert create_response.status_code == 201

    update_response = client.patch(
        f"/api/v1/agents/{slug}",
        headers=headers,
        json={
            "manifest_json": {
                "instructions": f"Run {title} checks.",
                "entrypoints": [f"run_{slug.replace('-', '_')}"],
            },
            "export_targets": ["codex"],
        },
    )
    assert update_response.status_code == 200

    publish_response = client.post(f"/api/v1/agents/{slug}/publish", headers=headers)
    assert publish_response.status_code == 200


def _publish_team(client: TestClient, *, headers: dict[str, str], slug: str) -> None:
    """Create and publish a minimal team."""
    create_response = client.post(
        "/api/v1/teams",
        headers=headers,
        json={
            "slug": slug,
            "title": "Delivery Team",
            "description": "Run Codex over one repo task.",
        },
    )
    assert create_response.status_code == 201

    add_response = client.post(
        f"/api/v1/teams/{slug}/items",
        headers=headers,
        json={
            "agent_slug": "delivery-orchestrator",
            "role_name": "orchestrator",
            "is_required": True,
        },
    )
    assert add_response.status_code == 200

    publish_response = client.post(f"/api/v1/teams/{slug}/publish", headers=headers)
    assert publish_response.status_code == 200


def _bundle_bytes(files: dict[str, str]) -> bytes:
    """Return zip bytes for one in-memory bundle."""
    buffer = BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def _workspace() -> WorkspaceRead:
    """Return one normalized workspace payload."""
    return WorkspaceRead(
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
        status="prepared",
        created_at="2026-03-08T10:00:00Z",
        updated_at="2026-03-08T10:00:00Z",
    )


def _execution_config(
    *,
    source_path: str | None = None,
    setup_commands: list[str] | None = None,
    check_commands: list[str] | None = None,
) -> WorkspaceExecutionConfigRead:
    """Return one normalized repo execution config payload for tests."""
    return WorkspaceExecutionConfigRead(
        source_path=source_path,
        run_working_directory=".",
        setup_working_directory=".",
        setup_commands=setup_commands or [],
        check_working_directory=".",
        check_commands=check_commands or [],
    )


def test_create_run_prepares_workspace_and_records_status_events(
    client: TestClient,
    monkeypatch,
) -> None:
    """Creating a run should prepare workspace state and record lifecycle events."""
    headers = _auth_headers(
        client,
        email="runner@example.com",
        display_name="Runner",
    )
    _publish_agent(
        client,
        headers=headers,
        slug="delivery-orchestrator",
        title="Delivery Orchestrator",
    )
    _publish_team(client, headers=headers, slug="delivery-team")

    monkeypatch.setattr(
        HostExecutionReadinessService,
        "build_readiness",
        lambda self: SimpleNamespace(effective_ready=True),
    )
    monkeypatch.setattr(
        GitHubProxyService,
        "get_repo",
        lambda self, owner, repo: GitHubRepoRead(
            owner=owner,
            name=repo,
            full_name=f"{owner}/{repo}",
            description="Demo repo",
            url=f"https://github.com/{owner}/{repo}",
            is_private=False,
            default_branch="main",
        ),
    )
    monkeypatch.setattr(
        GitHubProxyService,
        "get_issue",
        lambda self, owner, repo, number: GitHubIssueDetailRead(
            number=number,
            title="Fix run preparation flow",
            body="Implement the workspace preparation foundation.",
            state="open",
            url=f"https://github.com/{owner}/{repo}/issues/{number}",
            comments=[],
        ),
    )
    monkeypatch.setattr(
        WorkspaceProxyService,
        "prepare_workspace",
        lambda self, payload: _workspace(),
    )
    monkeypatch.setattr(
        WorkspaceProxyService,
        "materialize_workspace",
        lambda self, workspace_id, payload: _workspace().model_copy(
            update={
                "has_changes": True,
                "changed_files": [file.path for file in payload.files],
            }
        ),
    )
    monkeypatch.setattr(
        WorkspaceProxyService,
        "get_execution_config",
        lambda self, workspace_id: _execution_config(source_path=".team-agent-platform.toml"),
    )
    monkeypatch.setattr(
        ExportService,
        "build_download_artifact",
        lambda self, **kwargs: (
            "delivery-team-codex.zip",
            _bundle_bytes(
                {
                    ".codex/config.toml": (
                        "[features]\n"
                        "multi_agent = true\n\n"
                        '[agents."orchestrator"]\n'
                        'description = "Orchestrator"\n'
                        'config_file = "agents/orchestrator.toml"\n'
                    ),
                    ".codex/agents/orchestrator.toml": 'description = "Orchestrator"\n',
                }
            ),
            "application/zip",
        ),
    )
    monkeypatch.setattr(
        CodexProxyService,
        "start_session",
        lambda self, payload: CodexSessionRead(
            run_id=payload.run_id,
            workspace_id=payload.workspace_id,
            repo_path="/tmp/ws-1/repo",
            command=["codex", "exec", "--json"],
            status="running",
            pid=12345,
            started_at="2026-03-08T10:06:00Z",
            last_output_offset=0,
        ),
    )
    monkeypatch.setattr(
        CodexProxyService,
        "get_session",
        lambda self, run_id: CodexSessionRead(
            run_id=run_id,
            workspace_id="ws-1",
            repo_path="/tmp/ws-1/repo",
            command=["codex", "exec", "--json"],
            status="running",
            pid=12345,
            started_at="2026-03-08T10:06:00Z",
            last_output_offset=1,
        ),
    )
    monkeypatch.setattr(
        CodexProxyService,
        "get_events",
        lambda self, run_id, offset: CodexSessionEventsResponse(
            session=CodexSessionRead(
                run_id=run_id,
                workspace_id="ws-1",
                repo_path="/tmp/ws-1/repo",
                command=["codex", "exec", "--json"],
                status="running",
                pid=12345,
                started_at="2026-03-08T10:06:00Z",
                last_output_offset=1,
            ),
            items=[
                CodexTerminalChunk(
                    offset=0,
                    text="starting codex\n",
                    created_at="2026-03-08T10:06:01Z",
                )
            ]
            if offset == 0
            else [],
            next_offset=1,
        ),
    )

    create_response = client.post(
        "/api/v1/runs",
        headers=headers,
        json={
            "team_slug": "delivery-team",
            "repo_owner": "stemirkhan",
            "repo_name": "team-agent-platform",
            "issue_number": 17,
            "task_text": "Keep the initial run narrow and materialize `.codex` plus `TASK.md`.",
            "codex": {
                "model": "gpt-5.3-codex-spark",
                "model_reasoning_effort": "medium",
                "sandbox_mode": "workspace-write",
            },
        },
    )
    assert create_response.status_code == 201
    payload = create_response.json()
    assert payload["status"] == "running"
    assert payload["workspace_id"] == "ws-1"
    assert payload["runtime_target"] == "codex"
    assert payload["issue_number"] == 17
    assert payload["working_branch"] == "tap/team-agent-platform/demo-branch"

    run_id = payload["id"]

    list_response = client.get("/api/v1/runs", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    get_response = client.get(f"/api/v1/runs/{run_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Fix run preparation flow"

    terminal_session_response = client.get(
        f"/api/v1/runs/{run_id}/terminal/session",
        headers=headers,
    )
    assert terminal_session_response.status_code == 200
    assert terminal_session_response.json()["status"] == "running"

    terminal_events_response = client.get(
        f"/api/v1/runs/{run_id}/terminal/events?offset=0",
        headers=headers,
    )
    assert terminal_events_response.status_code == 200
    assert terminal_events_response.json()["items"][0]["text"] == "starting codex\n"

    events_response = client.get(f"/api/v1/runs/{run_id}/events", headers=headers)
    assert events_response.status_code == 200
    bundle_events = [
        item["payload_json"]
        for item in events_response.json()["items"]
        if item["event_type"] == "note"
        and item["payload_json"]
        and item["payload_json"].get("kind") == "codex_bundle"
    ]
    assert len(bundle_events) == 1
    assert bundle_events[0]["multi_agent_enabled"] is True
    assert bundle_events[0]["configured_agents"] == ["orchestrator"]
    assert bundle_events[0]["task_markdown"].startswith("# Fix run preparation flow")
    statuses = [
        item["payload_json"]["status"]
        for item in events_response.json()["items"]
        if item["event_type"] == "status"
    ]
    assert statuses == [
        "queued",
        "preparing",
        "cloning_repo",
        "materializing_team",
        "starting_codex",
        "running",
    ]


def test_create_run_returns_failed_state_when_workspace_prepare_breaks(
    client: TestClient,
    monkeypatch,
) -> None:
    """Preparation failures after run creation should persist a failed run."""
    headers = _auth_headers(
        client,
        email="runner-fail@example.com",
        display_name="Runner Fail",
    )
    _publish_agent(
        client,
        headers=headers,
        slug="delivery-orchestrator",
        title="Delivery Orchestrator",
    )
    _publish_team(client, headers=headers, slug="delivery-team-fail")

    monkeypatch.setattr(
        HostExecutionReadinessService,
        "build_readiness",
        lambda self: SimpleNamespace(effective_ready=True),
    )
    monkeypatch.setattr(
        GitHubProxyService,
        "get_repo",
        lambda self, owner, repo: GitHubRepoRead(
            owner=owner,
            name=repo,
            full_name=f"{owner}/{repo}",
            description="Demo repo",
            url=f"https://github.com/{owner}/{repo}",
            is_private=False,
            default_branch="main",
        ),
    )
    monkeypatch.setattr(
        WorkspaceProxyService,
        "prepare_workspace",
        lambda self, payload: (_ for _ in ()).throw(
            WorkspaceProxyServiceError(
                503,
                "Git authentication failed while trying to clone repository.",
            )
        ),
    )
    monkeypatch.setattr(
        WorkspaceProxyService,
        "get_execution_config",
        lambda self, workspace_id: _execution_config(),
    )

    create_response = client.post(
        "/api/v1/runs",
        headers=headers,
        json={
            "team_slug": "delivery-team-fail",
            "repo_owner": "stemirkhan",
            "repo_name": "team-agent-platform",
            "task_text": "Try to prepare the workspace.",
        },
    )
    assert create_response.status_code == 201
    payload = create_response.json()
    assert payload["status"] == "failed"
    assert "Git authentication failed" in payload["error_message"]

    events_response = client.get(f"/api/v1/runs/{payload['id']}/events", headers=headers)
    assert events_response.status_code == 200
    event_types = [item["event_type"] for item in events_response.json()["items"]]
    assert event_types[-1] == "error"


def test_list_runs_supports_repository_filter(
    client: TestClient,
    monkeypatch,
) -> None:
    """Run list should support filtering by repository full name."""
    headers = _auth_headers(
        client,
        email="runner-filter@example.com",
        display_name="Runner Filter",
    )
    _publish_agent(
        client,
        headers=headers,
        slug="delivery-orchestrator",
        title="Delivery Orchestrator",
    )
    _publish_team(client, headers=headers, slug="delivery-team-filter")

    monkeypatch.setattr(
        HostExecutionReadinessService,
        "build_readiness",
        lambda self: SimpleNamespace(effective_ready=True),
    )
    monkeypatch.setattr(
        GitHubProxyService,
        "get_repo",
        lambda self, owner, repo: GitHubRepoRead(
            owner=owner,
            name=repo,
            full_name=f"{owner}/{repo}",
            description="Demo repo",
            url=f"https://github.com/{owner}/{repo}",
            is_private=False,
            default_branch="main",
        ),
    )
    monkeypatch.setattr(
        WorkspaceProxyService,
        "prepare_workspace",
        lambda self, payload: _workspace(),
    )
    monkeypatch.setattr(
        WorkspaceProxyService,
        "materialize_workspace",
        lambda self, workspace_id, payload: _workspace().model_copy(
            update={"has_changes": True, "changed_files": [file.path for file in payload.files]}
        ),
    )
    monkeypatch.setattr(
        WorkspaceProxyService,
        "get_execution_config",
        lambda self, workspace_id: _execution_config(source_path=".team-agent-platform.toml"),
    )
    monkeypatch.setattr(
        ExportService,
        "build_download_artifact",
        lambda self, **kwargs: (
            "delivery-team-filter-codex.zip",
            _bundle_bytes(
                {
                    ".codex/config.toml": "[features]\nmulti_agent = true\n",
                    ".codex/agents/orchestrator.toml": 'description = "Orchestrator"\n',
                }
            ),
            "application/zip",
        ),
    )
    monkeypatch.setattr(
        CodexProxyService,
        "start_session",
        lambda self, payload: CodexSessionRead(
            run_id=payload.run_id,
            workspace_id=payload.workspace_id,
            repo_path="/tmp/ws-1/repo",
            command=["codex", "exec", "--json"],
            status="running",
            pid=12345,
            started_at="2026-03-08T10:06:00Z",
            last_output_offset=0,
        ),
    )
    monkeypatch.setattr(
        CodexProxyService,
        "get_session",
        lambda self, run_id: CodexSessionRead(
            run_id=run_id,
            workspace_id="ws-1",
            repo_path="/tmp/ws-1/repo",
            command=["codex", "exec", "--json"],
            status="running",
            pid=12345,
            started_at="2026-03-08T10:06:00Z",
            last_output_offset=0,
        ),
    )

    for owner, repo in [
        ("stemirkhan", "team-agent-platform"),
        ("stemirkhan", "agent-ops-demo"),
    ]:
        create_response = client.post(
            "/api/v1/runs",
            headers=headers,
            json={
                "team_slug": "delivery-team-filter",
                "repo_owner": owner,
                "repo_name": repo,
                "task_text": f"Run delivery workflow for {owner}/{repo}.",
            },
        )
        assert create_response.status_code == 201

    list_response = client.get(
        "/api/v1/runs?repo=stemirkhan/team-agent-platform",
        headers=headers,
    )
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["repo_full_name"] == "stemirkhan/team-agent-platform"


def test_get_run_syncs_terminal_completion_and_cancel_endpoint(
    client: TestClient,
    monkeypatch,
) -> None:
    """Run detail should reconcile host session completion and support cancel."""
    headers = _auth_headers(
        client,
        email="runner-sync@example.com",
        display_name="Runner Sync",
    )
    _publish_agent(
        client,
        headers=headers,
        slug="delivery-orchestrator",
        title="Delivery Orchestrator",
    )
    _publish_team(client, headers=headers, slug="delivery-team-sync")

    monkeypatch.setattr(
        HostExecutionReadinessService,
        "build_readiness",
        lambda self: SimpleNamespace(effective_ready=True),
    )
    monkeypatch.setattr(
        GitHubProxyService,
        "get_repo",
        lambda self, owner, repo: GitHubRepoRead(
            owner=owner,
            name=repo,
            full_name=f"{owner}/{repo}",
            description="Demo repo",
            url=f"https://github.com/{owner}/{repo}",
            is_private=False,
            default_branch="main",
        ),
    )
    monkeypatch.setattr(
        WorkspaceProxyService,
        "prepare_workspace",
        lambda self, payload: _workspace(),
    )
    monkeypatch.setattr(
        WorkspaceProxyService,
        "materialize_workspace",
        lambda self, workspace_id, payload: _workspace().model_copy(
            update={"has_changes": True, "changed_files": ["TASK.md"]}
        ),
    )
    monkeypatch.setattr(
        WorkspaceProxyService,
        "get_execution_config",
        lambda self, workspace_id: _execution_config(
            source_path=".team-agent-platform.toml",
            check_commands=["make compose-config"],
        ),
    )
    monkeypatch.setattr(
        WorkspaceProxyService,
        "get_workspace",
        lambda self, workspace_id: _workspace().model_copy(
            update={
                "status": "pull_request_created",
                "last_commit_sha": "abcdef1234567890",
                "pull_request_number": 42,
                "pull_request_url": "https://github.com/stemirkhan/team-agent-platform/pull/42",
            }
        ),
    )
    scm_calls: list[str] = []
    monkeypatch.setattr(
        WorkspaceProxyService,
        "run_commands",
        lambda self, workspace_id, payload: WorkspaceCommandsRunResponse(
            label=payload.label,
            working_directory=payload.working_directory,
            success=True,
            items=[
                WorkspaceCommandResult(
                    command="make compose-config",
                    exit_code=0,
                    output="ok",
                    started_at="2026-03-08T10:07:00Z",
                    finished_at="2026-03-08T10:07:02Z",
                    succeeded=True,
                )
            ],
        ),
    )
    monkeypatch.setattr(
        WorkspaceProxyService,
        "cleanup_workspace",
        lambda self, workspace_id: scm_calls.append("cleanup")
        or _workspace().model_copy(
            update={"has_changes": True, "changed_files": ["apps/backend/app.py"]}
        ),
    )
    monkeypatch.setattr(
        WorkspaceProxyService,
        "commit_workspace",
        lambda self, workspace_id, payload: scm_calls.append(f"commit:{payload.message}")
        or _workspace().model_copy(
            update={
                "status": "committed",
                "has_changes": False,
                "changed_files": [],
                "last_commit_sha": "abcdef1234567890",
                "last_commit_message": payload.message,
            }
        ),
    )
    monkeypatch.setattr(
        WorkspaceProxyService,
        "push_workspace",
        lambda self, workspace_id: scm_calls.append("push")
        or _workspace().model_copy(update={"status": "pushed"}),
    )
    monkeypatch.setattr(
        WorkspaceProxyService,
        "create_pull_request",
        lambda self, workspace_id, payload: scm_calls.append(f"pr:{payload.title}")
        or _workspace().model_copy(
            update={
                "status": "pull_request_created",
                "pull_request_number": 42,
                "pull_request_url": "https://github.com/stemirkhan/team-agent-platform/pull/42",
            }
        ),
    )
    monkeypatch.setattr(
        ExportService,
        "build_download_artifact",
        lambda self, **kwargs: (
            "delivery-team-sync-codex.zip",
            _bundle_bytes(
                {
                    ".codex/config.toml": "[features]\nmulti_agent = true\n",
                }
            ),
            "application/zip",
        ),
    )
    monkeypatch.setattr(
        CodexProxyService,
        "start_session",
        lambda self, payload: CodexSessionRead(
            run_id=payload.run_id,
            workspace_id=payload.workspace_id,
            repo_path="/tmp/ws-1/repo",
            command=["codex", "exec", "--json"],
            status="running",
            pid=12345,
            started_at="2026-03-08T10:06:00Z",
            last_output_offset=0,
        ),
    )
    monkeypatch.setattr(
        CodexProxyService,
        "get_session",
        lambda self, run_id: CodexSessionRead(
            run_id=run_id,
            workspace_id="ws-1",
            repo_path="/tmp/ws-1/repo",
            command=["codex", "exec", "--json"],
            status="completed",
            pid=12345,
            exit_code=0,
            summary_text="Codex finished successfully.",
            started_at="2026-03-08T10:06:00Z",
            finished_at="2026-03-08T10:08:00Z",
            last_output_offset=4,
        ),
    )
    monkeypatch.setattr(
        CodexProxyService,
        "cancel_session",
        lambda self, run_id: CodexSessionRead(
            run_id=run_id,
            workspace_id="ws-1",
            repo_path="/tmp/ws-1/repo",
            command=["codex", "exec", "--json"],
            status="cancelled",
            pid=12345,
            exit_code=None,
            started_at="2026-03-08T10:06:00Z",
            finished_at="2026-03-08T10:07:00Z",
            last_output_offset=2,
        ),
    )
    monkeypatch.setattr(
        CodexProxyService,
        "get_events",
        lambda self, run_id, offset: CodexSessionEventsResponse(
            session=CodexSessionRead(
                run_id=run_id,
                workspace_id="ws-1",
                repo_path="/tmp/ws-1/repo",
                command=["codex", "exec", "--json"],
                status="completed",
                pid=12345,
                exit_code=0,
                summary_text="Codex finished successfully.",
                started_at="2026-03-08T10:06:00Z",
                finished_at="2026-03-08T10:08:00Z",
                last_output_offset=4,
            ),
            items=[
                CodexTerminalChunk(
                    offset=0,
                    text=(
                        '{"type":"item.completed","item":{"type":"command_execution",'
                        '"command":"sed -n '
                        '\'1,220p\' '
                        '.codex/skills/frontend-product-engineer-frontend-ux-review/SKILL.md",'
                        '"aggregated_output":"ok","exit_code":0,"status":"completed"}}\n'
                        '{"type":"item.completed","item":{"type":"agent_message","text":"Использую '
                        '`frontend-ux-review` для фронтенд-оценки."}}\n'
                    ),
                    created_at="2026-03-08T10:07:30Z",
                )
            ]
            if offset == 0
            else [],
            next_offset=1,
        ),
    )

    create_response = client.post(
        "/api/v1/runs",
        headers=headers,
        json={
            "team_slug": "delivery-team-sync",
            "repo_owner": "stemirkhan",
            "repo_name": "team-agent-platform",
            "task_text": "Run codex.",
        },
    )
    assert create_response.status_code == 201
    run_id = create_response.json()["id"]

    get_response = client.get(f"/api/v1/runs/{run_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "completed"
    assert get_response.json()["summary"] == "Codex finished successfully."
    assert (
        get_response.json()["pr_url"]
        == "https://github.com/stemirkhan/team-agent-platform/pull/42"
    )
    report = get_response.json()["run_report"]
    assert report is not None
    phases = {item["key"]: item for item in report["phases"]}
    assert phases["preparation"]["status"] == "completed"
    assert phases["setup"]["status"] == "not_available"
    assert phases["codex"]["status"] == "completed"
    assert phases["checks"]["status"] == "completed"
    assert phases["checks"]["commands"][0]["command"] == "make compose-config"
    assert phases["checks"]["commands"][0]["output"] == "ok"
    assert phases["git_pr"]["status"] == "completed"
    assert phases["git_pr"]["meta"]["working_branch"] == "tap/team-agent-platform/demo-branch"
    assert phases["git_pr"]["meta"]["commit_sha"] == "abcdef1234567890"
    assert (
        phases["git_pr"]["meta"]["pr_url"]
        == "https://github.com/stemirkhan/team-agent-platform/pull/42"
    )
    assert scm_calls[0] == "cleanup"
    assert scm_calls[1].startswith("commit:chore(run): apply codex changes for Run codex.")
    assert scm_calls[2] == "push"
    assert scm_calls[3] == "pr:[tap] Run codex."

    events_response = client.get(f"/api/v1/runs/{run_id}/events", headers=headers)
    assert events_response.status_code == 200
    trace_events = [
        item["payload_json"]
        for item in events_response.json()["items"]
        if item["event_type"] == "note"
        and item["payload_json"]
        and item["payload_json"].get("kind") == "codex_execution_trace"
    ]
    assert len(trace_events) == 1
    assert trace_events[0]["skill_refs"] == [
        "frontend-product-engineer-frontend-ux-review",
        "frontend-ux-review",
    ]
    assert trace_events[0]["delegation_markers"] == []
    statuses = [
        item["payload_json"]["status"]
        for item in events_response.json()["items"]
        if item["event_type"] == "status"
    ]
    assert statuses[-6:] == [
        "committing",
        "running_checks",
        "committing",
        "pushing",
        "creating_pr",
        "completed",
    ]

    cancel_response = client.post(f"/api/v1/runs/{run_id}/cancel", headers=headers)
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "completed"


def test_get_run_completes_without_commit_when_only_materialized_files_changed(
    client: TestClient,
    monkeypatch,
) -> None:
    """Completed Codex sessions should skip commit/push/PR when cleanup leaves no repo changes."""
    headers = _auth_headers(
        client,
        email="runner-no-changes@example.com",
        display_name="Runner No Changes",
    )
    _publish_agent(
        client,
        headers=headers,
        slug="delivery-orchestrator",
        title="Delivery Orchestrator",
    )
    _publish_team(client, headers=headers, slug="delivery-team-no-changes")

    monkeypatch.setattr(
        HostExecutionReadinessService,
        "build_readiness",
        lambda self: SimpleNamespace(effective_ready=True),
    )
    monkeypatch.setattr(
        GitHubProxyService,
        "get_repo",
        lambda self, owner, repo: GitHubRepoRead(
            owner=owner,
            name=repo,
            full_name=f"{owner}/{repo}",
            description="Demo repo",
            url=f"https://github.com/{owner}/{repo}",
            is_private=False,
            default_branch="main",
        ),
    )
    monkeypatch.setattr(
        WorkspaceProxyService,
        "prepare_workspace",
        lambda self, payload: _workspace(),
    )
    monkeypatch.setattr(
        WorkspaceProxyService,
        "materialize_workspace",
        lambda self, workspace_id, payload: _workspace().model_copy(
            update={"has_changes": True, "changed_files": [".codex/config.toml", "TASK.md"]}
        ),
    )
    monkeypatch.setattr(
        WorkspaceProxyService,
        "get_execution_config",
        lambda self, workspace_id: _execution_config(),
    )
    monkeypatch.setattr(
        WorkspaceProxyService,
        "cleanup_workspace",
        lambda self, workspace_id: _workspace().model_copy(
            update={"has_changes": False, "changed_files": []}
        ),
    )
    monkeypatch.setattr(
        ExportService,
        "build_download_artifact",
        lambda self, **kwargs: (
            "delivery-team-no-changes-codex.zip",
            _bundle_bytes({".codex/config.toml": "[features]\nmulti_agent = true\n"}),
            "application/zip",
        ),
    )
    monkeypatch.setattr(
        CodexProxyService,
        "start_session",
        lambda self, payload: CodexSessionRead(
            run_id=payload.run_id,
            workspace_id=payload.workspace_id,
            repo_path="/tmp/ws-1/repo",
            command=["codex", "exec", "--json"],
            status="running",
            pid=12345,
            started_at="2026-03-08T10:06:00Z",
            last_output_offset=0,
        ),
    )
    monkeypatch.setattr(
        CodexProxyService,
        "get_session",
        lambda self, run_id: CodexSessionRead(
            run_id=run_id,
            workspace_id="ws-1",
            repo_path="/tmp/ws-1/repo",
            command=["codex", "exec", "--json"],
            status="completed",
            pid=12345,
            exit_code=0,
            summary_text="No code changes were required.",
            started_at="2026-03-08T10:06:00Z",
            finished_at="2026-03-08T10:08:00Z",
            last_output_offset=2,
        ),
    )
    monkeypatch.setattr(
        CodexProxyService,
        "get_events",
        lambda self, run_id, offset: CodexSessionEventsResponse(
            session=CodexSessionRead(
                run_id=run_id,
                workspace_id="ws-1",
                repo_path="/tmp/ws-1/repo",
                command=["codex", "exec", "--json"],
                status="completed",
                pid=12345,
                exit_code=0,
                summary_text="No code changes were required.",
                started_at="2026-03-08T10:06:00Z",
                finished_at="2026-03-08T10:08:00Z",
                last_output_offset=2,
            ),
            items=[] if offset > 0 else [],
            next_offset=0,
        ),
    )

    commit_called = False
    push_called = False
    pr_called = False

    monkeypatch.setattr(
        WorkspaceProxyService,
        "commit_workspace",
        lambda self, workspace_id, payload: (_ for _ in ()).throw(
            AssertionError("commit_workspace should not be called when there are no repo changes")
        ),
    )
    monkeypatch.setattr(
        WorkspaceProxyService,
        "push_workspace",
        lambda self, workspace_id: (_ for _ in ()).throw(
            AssertionError("push_workspace should not be called when there are no repo changes")
        ),
    )
    monkeypatch.setattr(
        WorkspaceProxyService,
        "create_pull_request",
        lambda self, workspace_id, payload: (_ for _ in ()).throw(
            AssertionError(
                "create_pull_request should not be called when there are no repo changes"
            )
        ),
    )

    create_response = client.post(
        "/api/v1/runs",
        headers=headers,
        json={
            "team_slug": "delivery-team-no-changes",
            "repo_owner": "stemirkhan",
            "repo_name": "team-agent-platform",
            "task_text": "Run codex but do not change the repo.",
        },
    )
    assert create_response.status_code == 201
    run_id = create_response.json()["id"]

    get_response = client.get(f"/api/v1/runs/{run_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "completed"
    assert get_response.json()["pr_url"] is None
    assert commit_called is False
    assert push_called is False
    assert pr_called is False

    events_response = client.get(f"/api/v1/runs/{run_id}/events", headers=headers)
    assert events_response.status_code == 200
    messages = [
        item["payload_json"]["message"]
        for item in events_response.json()["items"]
        if item["event_type"] == "status"
    ]
    assert "Codex session completed with no repository changes to commit." in messages


def test_get_run_fails_when_codex_session_state_is_lost(
    client: TestClient,
    monkeypatch,
) -> None:
    """A lost host-side Codex session must not leave the run stuck forever."""
    headers = _auth_headers(
        client,
        email="runner-lost-session@example.com",
        display_name="Runner Lost Session",
    )
    _publish_agent(
        client,
        headers=headers,
        slug="delivery-orchestrator",
        title="Delivery Orchestrator",
    )
    _publish_team(client, headers=headers, slug="delivery-team-lost-session")

    monkeypatch.setattr(
        HostExecutionReadinessService,
        "build_readiness",
        lambda self: SimpleNamespace(effective_ready=True),
    )
    monkeypatch.setattr(
        GitHubProxyService,
        "get_repo",
        lambda self, owner, repo: GitHubRepoRead(
            owner=owner,
            name=repo,
            full_name=f"{owner}/{repo}",
            description="Demo repo",
            url=f"https://github.com/{owner}/{repo}",
            is_private=False,
            default_branch="main",
        ),
    )
    monkeypatch.setattr(
        WorkspaceProxyService,
        "prepare_workspace",
        lambda self, payload: _workspace(),
    )
    monkeypatch.setattr(
        WorkspaceProxyService,
        "materialize_workspace",
        lambda self, workspace_id, payload: _workspace().model_copy(
            update={"has_changes": True, "changed_files": ["TASK.md"]}
        ),
    )
    monkeypatch.setattr(
        WorkspaceProxyService,
        "get_execution_config",
        lambda self, workspace_id: _execution_config(),
    )
    monkeypatch.setattr(
        ExportService,
        "build_download_artifact",
        lambda self, **kwargs: (
            "delivery-team-lost-session-codex.zip",
            _bundle_bytes({".codex/config.toml": "[features]\nmulti_agent = true\n"}),
            "application/zip",
        ),
    )
    monkeypatch.setattr(
        CodexProxyService,
        "start_session",
        lambda self, payload: CodexSessionRead(
            run_id=payload.run_id,
            workspace_id=payload.workspace_id,
            repo_path="/tmp/ws-1/repo",
            command=["codex", "exec", "--json"],
            status="running",
            pid=12345,
            started_at="2026-03-08T10:06:00Z",
            last_output_offset=0,
        ),
    )

    def _missing_session(self, run_id):
        raise CodexProxyServiceError(
            404,
            "Codex session not found.",
        )

    monkeypatch.setattr(CodexProxyService, "get_session", _missing_session)

    create_response = client.post(
        "/api/v1/runs",
        headers=headers,
        json={
            "team_slug": "delivery-team-lost-session",
            "repo_owner": "stemirkhan",
            "repo_name": "team-agent-platform",
            "task_text": "Run codex and simulate a lost session.",
        },
    )
    assert create_response.status_code == 201
    run_id = create_response.json()["id"]

    get_response = client.get(f"/api/v1/runs/{run_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "failed"
    assert "session state was lost" in get_response.json()["error_message"].lower()
