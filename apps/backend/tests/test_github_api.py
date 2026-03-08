"""Tests for GitHub proxy endpoints."""

from fastapi.testclient import TestClient

from app.api.v1 import github
from app.schemas.github import (
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


def test_github_repo_endpoints_return_normalized_payloads(client: TestClient, monkeypatch) -> None:
    """Repo and issue endpoints should expose normalized host-executor data."""
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
        github.github_proxy_service,
        "list_repos",
        lambda owner, limit, query: GitHubRepoListResponse(
            items=[repo_payload],
            total=1,
            limit=limit,
        ),
    )
    monkeypatch.setattr(github.github_proxy_service, "get_repo", lambda owner, repo: repo_payload)
    monkeypatch.setattr(
        github.github_proxy_service,
        "list_issues",
        lambda owner, repo, state, limit: GitHubIssueListResponse(
            items=[issue], total=1, limit=limit, state=state
        ),
    )
    monkeypatch.setattr(
        github.github_proxy_service,
        "get_issue",
        lambda owner, repo, number: issue_detail,
    )
    monkeypatch.setattr(
        github.github_proxy_service,
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
        github.github_proxy_service,
        "add_labels",
        lambda owner, repo, number, payload: GitHubIssueDetailRead(
            **issue_detail.model_dump(exclude={"labels"}),
            labels=sorted(set(issue_detail.labels + payload.labels)),
        ),
    )
    monkeypatch.setattr(
        github.github_proxy_service,
        "remove_label",
        lambda owner, repo, number, label_name: GitHubIssueDetailRead(
            **issue_detail.model_dump(exclude={"labels"}),
            labels=[label for label in issue_detail.labels if label != label_name],
        ),
    )
    monkeypatch.setattr(
        github.github_proxy_service,
        "list_pulls",
        lambda owner, repo, state, limit: GitHubPullListResponse(
            items=[pull], total=1, limit=limit, state=state
        ),
    )
    monkeypatch.setattr(
        github.github_proxy_service,
        "get_pull",
        lambda owner, repo, number: pull,
    )
    monkeypatch.setattr(
        github.github_proxy_service,
        "get_pull_checks",
        lambda owner, repo, number: pull_checks,
    )

    repo_list_response = client.get("/api/v1/github/repos?owner=stemirkhan&limit=10&q=team")
    assert repo_list_response.status_code == 200
    assert repo_list_response.json()["items"][0]["full_name"] == "stemirkhan/team-agent-platform"

    repo_response = client.get("/api/v1/github/repos/stemirkhan/team-agent-platform")
    assert repo_response.status_code == 200
    assert repo_response.json()["default_branch"] == "main"

    issues_response = client.get(
        "/api/v1/github/repos/stemirkhan/team-agent-platform/issues?state=all"
    )
    assert issues_response.status_code == 200
    assert issues_response.json()["items"][0]["number"] == 12

    issue_response = client.get("/api/v1/github/repos/stemirkhan/team-agent-platform/issues/12")
    assert issue_response.status_code == 200
    assert issue_response.json()["comments_count"] == 3
    assert issue_response.json()["comments"][0]["body"] == "First tracker comment"

    comment_response = client.post(
        "/api/v1/github/repos/stemirkhan/team-agent-platform/issues/12/comments",
        json=GitHubIssueCommentCreate(body="New note from UI").model_dump(),
    )
    assert comment_response.status_code == 200
    assert comment_response.json()["comments_count"] == 2
    assert comment_response.json()["comments"][-1]["body"] == "New note from UI"

    labels_response = client.post(
        "/api/v1/github/repos/stemirkhan/team-agent-platform/issues/12/labels",
        json=GitHubIssueLabelsUpdate(labels=["needs-review"]).model_dump(),
    )
    assert labels_response.status_code == 200
    assert "needs-review" in labels_response.json()["labels"]

    remove_label_response = client.delete(
        "/api/v1/github/repos/stemirkhan/team-agent-platform/issues/12/labels/mvp"
    )
    assert remove_label_response.status_code == 200
    assert "mvp" not in remove_label_response.json()["labels"]

    pulls_response = client.get(
        "/api/v1/github/repos/stemirkhan/team-agent-platform/pulls?state=open"
    )
    assert pulls_response.status_code == 200
    assert pulls_response.json()["items"][0]["head_ref_name"] == "feat/pr-browser"

    pull_response = client.get("/api/v1/github/repos/stemirkhan/team-agent-platform/pulls/24")
    assert pull_response.status_code == 200
    assert pull_response.json()["mergeable"] == "MERGEABLE"

    pull_checks_response = client.get(
        "/api/v1/github/repos/stemirkhan/team-agent-platform/pulls/24/checks"
    )
    assert pull_checks_response.status_code == 200
    assert pull_checks_response.json()["summary"]["pass_count"] == 1


def test_github_repo_endpoints_forward_proxy_errors(client: TestClient, monkeypatch) -> None:
    """Proxy errors should surface as API errors with readable details."""
    from app.services.github_proxy_service import GitHubProxyServiceError

    monkeypatch.setattr(
        github.github_proxy_service,
        "list_repos",
        lambda owner, limit, query: (_ for _ in ()).throw(
            GitHubProxyServiceError(503, "Host executor is unreachable.")
        ),
    )

    response = client.get("/api/v1/github/repos")
    assert response.status_code == 503
    assert response.json()["detail"] == "Host executor is unreachable."
