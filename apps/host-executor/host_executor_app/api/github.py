"""GitHub tracker endpoints backed by the host gh CLI."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Path, Query

from host_executor_app.schemas.github import (
    GitHubBranchListResponse,
    GitHubIssueCommentCreate,
    GitHubIssueDetailRead,
    GitHubIssueLabelsUpdate,
    GitHubIssueListResponse,
    GitHubPullChecksResponse,
    GitHubPullListResponse,
    GitHubPullRead,
    GitHubRepoListResponse,
    GitHubRepoRead,
)
from host_executor_app.services.github_scm_service import GitHubScmService, GitHubScmServiceError
from host_executor_app.services.github_tracker_service import (
    GitHubTrackerService,
    GitHubTrackerServiceError,
)

router = APIRouter(prefix="/github", tags=["github"])
github_tracker_service = GitHubTrackerService()
github_scm_service = GitHubScmService()


@router.get("/repos", response_model=GitHubRepoListResponse)
def list_repos(
    owner: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=30, ge=1, le=100),
    search: str | None = Query(default=None, alias="q", max_length=255),
) -> GitHubRepoListResponse:
    """Return repositories visible to the current gh-authenticated user."""
    try:
        return github_tracker_service.list_repos(owner=owner, limit=limit, query=search)
    except GitHubTrackerServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/repos/{owner}/{repo}", response_model=GitHubRepoRead)
def get_repo(
    owner: str = Path(min_length=1),
    repo: str = Path(min_length=1),
) -> GitHubRepoRead:
    """Return repository metadata for one repo."""
    try:
        return github_tracker_service.get_repo(owner=owner, repo=repo)
    except GitHubTrackerServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/repos/{owner}/{repo}/branches", response_model=GitHubBranchListResponse)
def list_branches(
    owner: str = Path(min_length=1),
    repo: str = Path(min_length=1),
    limit: int = Query(default=30, ge=1, le=100),
) -> GitHubBranchListResponse:
    """Return branches for a repository."""
    try:
        return github_tracker_service.list_branches(owner=owner, repo=repo, limit=limit)
    except GitHubTrackerServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/repos/{owner}/{repo}/issues", response_model=GitHubIssueListResponse)
def list_issues(
    owner: str = Path(min_length=1),
    repo: str = Path(min_length=1),
    state: Literal["open", "closed", "all"] = Query(default="open"),
    limit: int = Query(default=30, ge=1, le=100),
    search: str | None = Query(default=None, alias="q", max_length=255),
) -> GitHubIssueListResponse:
    """Return issues for a repository."""
    try:
        return github_tracker_service.list_issues(
            owner=owner,
            repo=repo,
            state=state,
            limit=limit,
            query=search,
        )
    except GitHubTrackerServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/repos/{owner}/{repo}/issues/{number}", response_model=GitHubIssueDetailRead)
def get_issue(
    owner: str = Path(min_length=1),
    repo: str = Path(min_length=1),
    number: int = Path(ge=1),
) -> GitHubIssueDetailRead:
    """Return one repository issue."""
    try:
        return github_tracker_service.get_issue(owner=owner, repo=repo, number=number)
    except GitHubTrackerServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post(
    "/repos/{owner}/{repo}/issues/{number}/comments",
    response_model=GitHubIssueDetailRead,
)
def add_issue_comment(
    payload: GitHubIssueCommentCreate,
    owner: str = Path(min_length=1),
    repo: str = Path(min_length=1),
    number: int = Path(ge=1),
) -> GitHubIssueDetailRead:
    """Add a comment to an issue and return the refreshed issue view."""
    try:
        return github_tracker_service.add_comment(
            owner=owner,
            repo=repo,
            number=number,
            payload=payload,
        )
    except GitHubTrackerServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post(
    "/repos/{owner}/{repo}/issues/{number}/labels",
    response_model=GitHubIssueDetailRead,
)
def add_issue_labels(
    payload: GitHubIssueLabelsUpdate,
    owner: str = Path(min_length=1),
    repo: str = Path(min_length=1),
    number: int = Path(ge=1),
) -> GitHubIssueDetailRead:
    """Add labels to an issue and return the refreshed issue view."""
    try:
        return github_tracker_service.add_labels(
            owner=owner,
            repo=repo,
            number=number,
            payload=payload,
        )
    except GitHubTrackerServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.delete(
    "/repos/{owner}/{repo}/issues/{number}/labels/{label_name}",
    response_model=GitHubIssueDetailRead,
)
def remove_issue_label(
    owner: str = Path(min_length=1),
    repo: str = Path(min_length=1),
    number: int = Path(ge=1),
    label_name: str = Path(min_length=1),
) -> GitHubIssueDetailRead:
    """Remove a label from an issue and return the refreshed issue view."""
    try:
        return github_tracker_service.remove_label(
            owner=owner,
            repo=repo,
            number=number,
            label=label_name,
        )
    except GitHubTrackerServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/repos/{owner}/{repo}/pulls", response_model=GitHubPullListResponse)
def list_pulls(
    owner: str = Path(min_length=1),
    repo: str = Path(min_length=1),
    state: Literal["open", "closed", "merged", "all"] = Query(default="open"),
    limit: int = Query(default=30, ge=1, le=100),
) -> GitHubPullListResponse:
    """Return pull requests for a repository."""
    try:
        return github_scm_service.list_pulls(owner=owner, repo=repo, state=state, limit=limit)
    except GitHubScmServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/repos/{owner}/{repo}/pulls/{number}", response_model=GitHubPullRead)
def get_pull(
    owner: str = Path(min_length=1),
    repo: str = Path(min_length=1),
    number: int = Path(ge=1),
) -> GitHubPullRead:
    """Return one repository pull request."""
    try:
        return github_scm_service.get_pull(owner=owner, repo=repo, number=number)
    except GitHubScmServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/repos/{owner}/{repo}/pulls/{number}/checks", response_model=GitHubPullChecksResponse)
def get_pull_checks(
    owner: str = Path(min_length=1),
    repo: str = Path(min_length=1),
    number: int = Path(ge=1),
) -> GitHubPullChecksResponse:
    """Return normalized checks for one pull request."""
    try:
        return github_scm_service.get_pull_checks(owner=owner, repo=repo, number=number)
    except GitHubScmServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
