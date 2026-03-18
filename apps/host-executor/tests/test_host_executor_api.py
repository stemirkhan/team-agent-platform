"""Smoke tests for the host executor bridge API."""

import threading
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from host_executor_app.api import claude as claude_api
from host_executor_app.api import codex as codex_api
from host_executor_app.api import github as github_api
from host_executor_app.core.config import get_settings
from host_executor_app.main import app
from host_executor_app.schemas.claude import (
    ClaudeSessionEventsResponse,
    ClaudeSessionRead,
    ClaudeSessionStart,
    ClaudeTerminalChunk,
)
from host_executor_app.schemas.codex import (
    CodexSessionEventsResponse,
    CodexSessionRead,
    CodexSessionStart,
    CodexTerminalChunk,
)
from host_executor_app.schemas.github import (
    GitHubBranchListResponse,
    GitHubBranchRead,
    GitHubIssueCommentCreate,
    GitHubIssueCommentRead,
    GitHubIssueDetailRead,
    GitHubIssueLabelsUpdate,
    GitHubIssueListResponse,
    GitHubIssueRead,
    GitHubPullCheckRead,
    GitHubPullChecksResponse,
    GitHubPullChecksSummary,
    GitHubPullListResponse,
    GitHubPullRead,
    GitHubRepoListResponse,
    GitHubRepoRead,
)
from host_executor_app.schemas.host import (
    HostDiagnosticsResponse,
    HostDiagnosticsTools,
    HostExecutorContext,
    HostToolDiagnostics,
    HostToolStatus,
)
from host_executor_app.services.host_diagnostics_service import HostDiagnosticsService
from host_executor_app.services.runtime_session_engine import BaseRuntimeSessionService


def _authorized_client() -> TestClient:
    """Return a TestClient that presents the shared backend secret."""
    return TestClient(
        app,
        headers={"X-TAP-Executor-Secret": get_settings().host_executor_shared_secret},
    )


def test_host_executor_healthz() -> None:
    """Health endpoint should report ok."""
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_host_executor_diagnostics_shape() -> None:
    """Diagnostics endpoint should return a normalized payload shape."""
    client = _authorized_client()

    response = client.get("/diagnostics")

    assert response.status_code == 200
    payload = response.json()
    assert "ready" in payload
    assert "tools" in payload
    assert "claude" in payload["tools"]
    assert "codex" in payload["tools"]


def test_host_executor_diagnostics_service_parses_tmux_two_part_version() -> None:
    """tmux outputs without a patch segment should still be treated as valid versions."""
    service = HostDiagnosticsService()

    version, version_ok, error_message = service._resolve_version(
        "/usr/bin/tmux",
        ["-V"],
        "3.2.0",
    )

    assert version == "3.4"
    assert version_ok is True
    assert error_message is None


def test_host_executor_diagnostics_service_uses_short_lived_cache(monkeypatch) -> None:
    """Repeated diagnostics requests should reuse a recent snapshot instead of re-running probes."""
    service = HostDiagnosticsService(cache_ttl_seconds=30.0)
    calls = {"count": 0}

    def fake_build_snapshot_live() -> HostDiagnosticsResponse:
        calls["count"] += 1
        return HostDiagnosticsResponse(
            generated_at=datetime.now(UTC),
            ready=True,
            pty_supported=True,
            durable_transport_ready=True,
            executor_context=HostExecutorContext(
                user="tester",
                home="/tmp/tester",
                cwd="/workspace",
                containerized=False,
                container_runtime=None,
            ),
            tools=HostDiagnosticsTools(
                git=HostToolDiagnostics(
                    name="git",
                    found=True,
                    path="/usr/bin/git",
                    version="2.43.0",
                    minimum_version="2.39.0",
                    version_ok=True,
                    auth_required=False,
                    auth_ok=None,
                    status=HostToolStatus.READY,
                    message="git ready",
                ),
                gh=HostToolDiagnostics(
                    name="gh",
                    found=True,
                    path="/usr/bin/gh",
                    version="2.86.0",
                    minimum_version="2.80.0",
                    version_ok=True,
                    auth_required=True,
                    auth_ok=True,
                    status=HostToolStatus.READY,
                    message="gh ready",
                ),
                codex=HostToolDiagnostics(
                    name="codex",
                    found=True,
                    path="/usr/bin/codex",
                    version="0.112.0",
                    minimum_version="0.100.0",
                    version_ok=True,
                    auth_required=True,
                    auth_ok=True,
                    status=HostToolStatus.READY,
                    message="codex ready",
                ),
                claude=HostToolDiagnostics(
                    name="claude",
                    found=True,
                    path="/usr/bin/claude",
                    version="2.1.71",
                    minimum_version="2.0.0",
                    version_ok=True,
                    auth_required=True,
                    auth_ok=True,
                    status=HostToolStatus.READY,
                    message="claude ready",
                ),
                tmux=HostToolDiagnostics(
                    name="tmux",
                    found=True,
                    path="/usr/bin/tmux",
                    version="3.4",
                    minimum_version="3.2.0",
                    version_ok=True,
                    auth_required=False,
                    auth_ok=None,
                    status=HostToolStatus.READY,
                    message="tmux ready",
                ),
            ),
            warnings=[],
        )

    monkeypatch.setattr(service, "_build_snapshot_live", fake_build_snapshot_live)

    first = service.build_snapshot()
    second = service.build_snapshot()
    third = service.build_snapshot(force_refresh=True)

    assert first.ready is True
    assert second.ready is True
    assert third.ready is True
    assert calls["count"] == 2


def test_runtime_session_engine_atomic_write_text_handles_parallel_writers(
    monkeypatch,
    tmp_path,
) -> None:
    """Concurrent writers should not contend on one shared temp file name."""
    target = tmp_path / "session.json"
    barrier = threading.Barrier(2)
    original_write_text = Path.write_text

    def delayed_write_text(self: Path, data: str, *args, **kwargs) -> int:
        result = original_write_text(self, data, *args, **kwargs)
        if self.parent == tmp_path and self.suffix == ".tmp":
            barrier.wait(timeout=5)
        return result

    monkeypatch.setattr(Path, "write_text", delayed_write_text)

    errors: list[Exception] = []

    def writer(content: str) -> None:
        try:
            BaseRuntimeSessionService._atomic_write_text(target, content)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    thread_a = threading.Thread(target=writer, args=("alpha",))
    thread_b = threading.Thread(target=writer, args=("beta",))
    thread_a.start()
    thread_b.start()
    thread_a.join()
    thread_b.join()

    assert errors == []
    assert target.read_text(encoding="utf-8") in {"alpha", "beta"}


def test_host_executor_github_repo_endpoints(monkeypatch) -> None:
    """GitHub endpoints should proxy normalized repo and issue payloads."""
    client = _authorized_client()

    repo_payload = GitHubRepoRead(
        owner="stemirkhan",
        name="team-agent-platform",
        full_name="stemirkhan/team-agent-platform",
        description="Local-first Codex execution platform.",
        url="https://github.com/stemirkhan/team-agent-platform",
        ssh_url="git@github.com:stemirkhan/team-agent-platform.git",
        is_private=True,
        visibility="PRIVATE",
        default_branch="main",
        has_issues_enabled=True,
        viewer_permission="ADMIN",
        updated_at="2026-03-08T00:00:00Z",
        pushed_at="2026-03-08T00:10:00Z",
    )
    branch_list = GitHubBranchListResponse(
        items=[
            GitHubBranchRead(name="main", is_default=True, is_protected=True),
            GitHubBranchRead(name="develop", is_default=False, is_protected=False),
        ],
        total=2,
        limit=10,
    )
    issue = GitHubIssueRead(
        number=12,
        title="Wire gh repo browser",
        body="Need repo and issue list.",
        state="OPEN",
        url="https://github.com/stemirkhan/team-agent-platform/issues/12",
        author_login="temirkhan",
        labels=["mvp", "github"],
        comments_count=3,
        created_at="2026-03-07T22:00:00Z",
        updated_at="2026-03-08T01:00:00Z",
    )
    issue_detail = GitHubIssueDetailRead(
        **issue.model_dump(),
        comments=[
            GitHubIssueCommentRead(
                id="comment-1",
                author_login="temirkhan",
                body="First tracker comment",
                url="https://github.com/stemirkhan/team-agent-platform/issues/12#issuecomment-1",
                created_at="2026-03-08T01:10:00Z",
                updated_at="2026-03-08T01:10:00Z",
            )
        ],
    )
    pull = GitHubPullRead(
        number=24,
        title="Add PR browser",
        body="Need pull request metadata and checks.",
        state="OPEN",
        url="https://github.com/stemirkhan/team-agent-platform/pull/24",
        author_login="temirkhan",
        labels=["mvp", "scm"],
        comments_count=2,
        is_draft=False,
        base_ref_name="main",
        head_ref_name="feat/pr-browser",
        merge_state_status="BLOCKED",
        mergeable="MERGEABLE",
        review_decision="REVIEW_REQUIRED",
        created_at="2026-03-08T02:00:00Z",
        updated_at="2026-03-08T03:00:00Z",
    )
    pull_checks = GitHubPullChecksResponse(
        items=[
            GitHubPullCheckRead(
                name="unit-tests",
                state="SUCCESS",
                bucket="pass",
                workflow="CI",
                description="All unit tests passed.",
                event="pull_request",
                link="https://github.com/stemirkhan/team-agent-platform/actions/runs/1",
                started_at="2026-03-08T03:00:00Z",
                completed_at="2026-03-08T03:05:00Z",
            )
        ],
        total=1,
        summary=GitHubPullChecksSummary(pass_count=1),
    )

    monkeypatch.setattr(
        github_api.github_tracker_service,
        "list_repos",
        lambda owner, limit, query: GitHubRepoListResponse(
            items=[repo_payload],
            total=1,
            limit=limit,
        ),
    )
    monkeypatch.setattr(
        github_api.github_tracker_service,
        "get_repo",
        lambda owner, repo: repo_payload,
    )
    monkeypatch.setattr(
        github_api.github_tracker_service,
        "list_branches",
        lambda owner, repo, limit: branch_list.model_copy(update={"limit": limit}),
    )
    monkeypatch.setattr(
        github_api.github_tracker_service,
        "list_issues",
        lambda owner, repo, state, limit, query: GitHubIssueListResponse(
            items=[issue],
            total=1,
            limit=limit,
            state=state,
        ),
    )
    monkeypatch.setattr(
        github_api.github_tracker_service,
        "get_issue",
        lambda owner, repo, number: issue_detail,
    )
    monkeypatch.setattr(
        github_api.github_tracker_service,
        "add_comment",
        lambda owner, repo, number, payload: GitHubIssueDetailRead(
            **issue_detail.model_dump(exclude={"comments_count", "comments"}),
            comments_count=2,
            comments=issue_detail.comments
            + [
                GitHubIssueCommentRead(
                    id="comment-2",
                    author_login="temirkhan",
                    body=payload.body,
                    url="https://github.com/stemirkhan/team-agent-platform/issues/12#issuecomment-2",
                    created_at="2026-03-08T01:20:00Z",
                    updated_at="2026-03-08T01:20:00Z",
                )
            ],
        ),
    )
    monkeypatch.setattr(
        github_api.github_tracker_service,
        "add_labels",
        lambda owner, repo, number, payload: GitHubIssueDetailRead(
            **issue_detail.model_dump(exclude={"labels"}),
            labels=sorted(set(issue_detail.labels + payload.labels)),
        ),
    )
    monkeypatch.setattr(
        github_api.github_tracker_service,
        "remove_label",
        lambda owner, repo, number, label: GitHubIssueDetailRead(
            **issue_detail.model_dump(exclude={"labels"}),
            labels=[current for current in issue_detail.labels if current != label],
        ),
    )
    monkeypatch.setattr(
        github_api.github_scm_service,
        "list_pulls",
        lambda owner, repo, state, limit: GitHubPullListResponse(
            items=[pull], total=1, limit=limit, state=state
        ),
    )
    monkeypatch.setattr(
        github_api.github_scm_service,
        "get_pull",
        lambda owner, repo, number: pull,
    )
    monkeypatch.setattr(
        github_api.github_scm_service,
        "get_pull_checks",
        lambda owner, repo, number: pull_checks,
    )

    repo_list_response = client.get("/github/repos?owner=stemirkhan&limit=10&q=team")
    assert repo_list_response.status_code == 200
    assert repo_list_response.json()["items"][0]["full_name"] == "stemirkhan/team-agent-platform"

    repo_response = client.get("/github/repos/stemirkhan/team-agent-platform")
    assert repo_response.status_code == 200
    assert repo_response.json()["default_branch"] == "main"

    branches_response = client.get("/github/repos/stemirkhan/team-agent-platform/branches?limit=10")
    assert branches_response.status_code == 200
    assert branches_response.json()["items"][0]["name"] == "main"
    assert branches_response.json()["items"][0]["is_default"] is True

    issues_response = client.get(
        "/github/repos/stemirkhan/team-agent-platform/issues?state=all&q=repo"
    )
    assert issues_response.status_code == 200
    assert issues_response.json()["items"][0]["number"] == 12

    issue_response = client.get("/github/repos/stemirkhan/team-agent-platform/issues/12")
    assert issue_response.status_code == 200
    assert issue_response.json()["comments_count"] == 3
    assert issue_response.json()["comments"][0]["body"] == "First tracker comment"

    comment_response = client.post(
        "/github/repos/stemirkhan/team-agent-platform/issues/12/comments",
        json=GitHubIssueCommentCreate(body="New note from UI").model_dump(),
    )
    assert comment_response.status_code == 200
    assert comment_response.json()["comments_count"] == 2
    assert comment_response.json()["comments"][-1]["body"] == "New note from UI"

    labels_response = client.post(
        "/github/repos/stemirkhan/team-agent-platform/issues/12/labels",
        json=GitHubIssueLabelsUpdate(labels=["needs-review"]).model_dump(),
    )
    assert labels_response.status_code == 200
    assert "needs-review" in labels_response.json()["labels"]

    remove_label_response = client.delete(
        "/github/repos/stemirkhan/team-agent-platform/issues/12/labels/mvp"
    )
    assert remove_label_response.status_code == 200
    assert "mvp" not in remove_label_response.json()["labels"]

    pulls_response = client.get("/github/repos/stemirkhan/team-agent-platform/pulls?state=open")
    assert pulls_response.status_code == 200
    assert pulls_response.json()["items"][0]["head_ref_name"] == "feat/pr-browser"

    pull_response = client.get("/github/repos/stemirkhan/team-agent-platform/pulls/24")
    assert pull_response.status_code == 200
    assert pull_response.json()["mergeable"] == "MERGEABLE"

    pull_checks_response = client.get(
        "/github/repos/stemirkhan/team-agent-platform/pulls/24/checks"
    )
    assert pull_checks_response.status_code == 200
    assert pull_checks_response.json()["summary"]["pass_count"] == 1


def test_host_executor_codex_session_endpoints(monkeypatch) -> None:
    """Codex endpoints should expose normalized session payloads."""
    client = _authorized_client()

    session = CodexSessionRead(
        run_id="run-1",
        workspace_id="ws-1",
        repo_path="/tmp/ws-1/repo",
        command=["codex", "exec", "--json"],
        status="running",
        pid=12345,
        started_at="2026-03-08T10:00:00Z",
        last_output_offset=1,
    )
    events = CodexSessionEventsResponse(
        session=session,
        items=[
            CodexTerminalChunk(
                offset=0,
                text="running codex\n",
                created_at="2026-03-08T10:00:01Z",
            )
        ],
        next_offset=1,
    )

    monkeypatch.setattr(
        codex_api.codex_session_service,
        "start_session",
        lambda payload: session,
    )
    monkeypatch.setattr(
        codex_api.codex_session_service,
        "get_session",
        lambda run_id: session,
    )
    monkeypatch.setattr(
        codex_api.codex_session_service,
        "get_events",
        lambda run_id, offset: events,
    )
    monkeypatch.setattr(
        codex_api.codex_session_service,
        "cancel_session",
        lambda run_id: session.model_copy(update={"status": "cancelled"}),
    )
    monkeypatch.setattr(
        codex_api.codex_session_service,
        "resume_session",
        lambda run_id: session.model_copy(update={"status": "resuming", "resume_attempt_count": 1}),
    )

    start_response = client.post(
        "/codex/sessions/start",
        json=CodexSessionStart(
            run_id="run-1",
            workspace_id="ws-1",
            prompt_text="Run TASK.md",
        ).model_dump(),
    )
    assert start_response.status_code == 201
    assert start_response.json()["status"] == "running"

    get_response = client.get("/codex/sessions/run-1")
    assert get_response.status_code == 200
    assert get_response.json()["repo_path"] == "/tmp/ws-1/repo"

    events_response = client.get("/codex/sessions/run-1/events?offset=0")
    assert events_response.status_code == 200
    assert events_response.json()["items"][0]["text"] == "running codex\n"

    cancel_response = client.post("/codex/sessions/run-1/cancel")
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"

    resume_response = client.post("/codex/sessions/run-1/resume")
    assert resume_response.status_code == 200
    assert resume_response.json()["status"] == "resuming"
    assert resume_response.json()["resume_attempt_count"] == 1


def test_host_executor_claude_session_endpoints(monkeypatch) -> None:
    """Claude endpoints should expose normalized session payloads."""
    client = _authorized_client()

    session = ClaudeSessionRead(
        run_id="run-claude-1",
        workspace_id="ws-claude-1",
        repo_path="/tmp/ws-claude-1/repo",
        command=[
            "claude",
            "-p",
            "--verbose",
            "--output-format",
            "stream-json",
            "--session-id",
            "88a7b103-6ca7-52f1-a774-a713ca889ed8",
        ],
        status="running",
        pid=23456,
        claude_session_id="88a7b103-6ca7-52f1-a774-a713ca889ed8",
        started_at="2026-03-14T10:00:00Z",
        last_output_offset=1,
    )
    events = ClaudeSessionEventsResponse(
        session=session,
        items=[
            ClaudeTerminalChunk(
                offset=0,
                text='{"type":"assistant","message":{"content":[{"type":"text","text":"running claude"}]}}\n',
                created_at="2026-03-14T10:00:01Z",
            )
        ],
        next_offset=1,
    )

    monkeypatch.setattr(
        claude_api.claude_session_service,
        "start_session",
        lambda payload: session,
    )
    monkeypatch.setattr(
        claude_api.claude_session_service,
        "get_session",
        lambda run_id: session,
    )
    monkeypatch.setattr(
        claude_api.claude_session_service,
        "get_events",
        lambda run_id, offset: events,
    )
    monkeypatch.setattr(
        claude_api.claude_session_service,
        "cancel_session",
        lambda run_id: session.model_copy(update={"status": "cancelled"}),
    )
    monkeypatch.setattr(
        claude_api.claude_session_service,
        "resume_session",
        lambda run_id: session.model_copy(update={"status": "resuming", "resume_attempt_count": 1}),
    )

    start_response = client.post(
        "/claude/sessions/start",
        json=ClaudeSessionStart(
            run_id="run-claude-1",
            workspace_id="ws-claude-1",
            prompt_text="Run TASK.md with Claude.",
        ).model_dump(),
    )
    assert start_response.status_code == 201
    assert start_response.json()["status"] == "running"

    get_response = client.get("/claude/sessions/run-claude-1")
    assert get_response.status_code == 200
    assert get_response.json()["repo_path"] == "/tmp/ws-claude-1/repo"

    events_response = client.get("/claude/sessions/run-claude-1/events?offset=0")
    assert events_response.status_code == 200
    assert "running claude" in events_response.json()["items"][0]["text"]

    cancel_response = client.post("/claude/sessions/run-claude-1/cancel")
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"

    resume_response = client.post("/claude/sessions/run-claude-1/resume")
    assert resume_response.status_code == 200
    assert resume_response.json()["status"] == "resuming"
    assert resume_response.json()["resume_attempt_count"] == 1
