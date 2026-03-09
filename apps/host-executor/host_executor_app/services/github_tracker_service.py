"""GitHub Tracker adapter backed by the host gh CLI."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

from host_executor_app.core.config import get_settings
from host_executor_app.schemas.github import (
    GitHubBranchListResponse,
    GitHubBranchRead,
    GitHubIssueCommentCreate,
    GitHubIssueCommentRead,
    GitHubIssueDetailRead,
    GitHubIssueLabelsUpdate,
    GitHubIssueListResponse,
    GitHubIssueRead,
    GitHubRepoListResponse,
    GitHubRepoRead,
)


@dataclass(slots=True)
class GitHubTrackerServiceError(Exception):
    """Normalized error raised when gh commands fail."""

    status_code: int
    detail: str


class GitHubTrackerService:
    """Provide normalized repo and issue reads through the GitHub CLI."""

    REPO_FIELDS = [
        "defaultBranchRef",
        "description",
        "hasIssuesEnabled",
        "isPrivate",
        "name",
        "nameWithOwner",
        "owner",
        "pushedAt",
        "sshUrl",
        "updatedAt",
        "url",
        "viewerPermission",
        "visibility",
    ]
    ISSUE_FIELDS = [
        "author",
        "body",
        "comments",
        "createdAt",
        "labels",
        "number",
        "state",
        "title",
        "updatedAt",
        "url",
    ]

    def __init__(self) -> None:
        self.settings = get_settings()

    def list_repos(
        self,
        owner: str | None,
        limit: int,
        query: str | None,
    ) -> GitHubRepoListResponse:
        """Return normalized repositories for the current gh-authenticated context."""
        args = ["repo", "list"]
        if owner:
            args.append(owner)
        args.extend(["--limit", str(limit), "--json", ",".join(self.REPO_FIELDS)])

        payload = self._run_json(args)
        if not isinstance(payload, list):
            raise GitHubTrackerServiceError(502, "GitHub CLI returned an unexpected repo list.")

        items = [self._normalize_repo(item) for item in payload if isinstance(item, dict)]
        if query:
            normalized_query = query.strip().lower()
            items = [
                item
                for item in items
                if normalized_query in item.full_name.lower()
                or normalized_query in item.name.lower()
                or normalized_query in (item.description or "").lower()
            ]

        return GitHubRepoListResponse(items=items, total=len(items), limit=limit)

    def get_repo(self, owner: str, repo: str) -> GitHubRepoRead:
        """Return normalized repository metadata for one repo."""
        payload = self._run_json(
            [
                "repo",
                "view",
                f"{owner}/{repo}",
                "--json",
                ",".join(self.REPO_FIELDS),
            ]
        )
        if not isinstance(payload, dict):
            raise GitHubTrackerServiceError(502, "GitHub CLI returned an unexpected repo payload.")
        return self._normalize_repo(payload)

    def list_branches(self, owner: str, repo: str, limit: int) -> GitHubBranchListResponse:
        """Return normalized branches for one repository."""
        repo_payload = self.get_repo(owner=owner, repo=repo)
        payload = self._run_json(
            [
                "api",
                f"repos/{owner}/{repo}/branches?per_page={limit}",
            ]
        )
        if not isinstance(payload, list):
            raise GitHubTrackerServiceError(502, "GitHub CLI returned an unexpected branch list.")

        items = [
            self._normalize_branch(item, default_branch=repo_payload.default_branch)
            for item in payload
            if isinstance(item, dict)
        ]
        return GitHubBranchListResponse(items=items, total=len(items), limit=limit)

    def list_issues(
        self,
        owner: str,
        repo: str,
        state: str,
        limit: int,
        query: str | None,
    ) -> GitHubIssueListResponse:
        """Return normalized issues for a repository."""
        args = [
            "issue",
            "list",
            "--repo",
            f"{owner}/{repo}",
            "--state",
            state,
            "--limit",
            str(limit),
            "--json",
            ",".join(self.ISSUE_FIELDS),
        ]
        if query:
            args.extend(["--search", query])

        payload = self._run_json(args)
        if not isinstance(payload, list):
            raise GitHubTrackerServiceError(502, "GitHub CLI returned an unexpected issue list.")

        items = [self._normalize_issue(item) for item in payload if isinstance(item, dict)]
        return GitHubIssueListResponse(items=items, total=len(items), limit=limit, state=state)

    def get_issue(self, owner: str, repo: str, number: int) -> GitHubIssueDetailRead:
        """Return normalized issue details for a repository issue."""
        payload = self._run_json(
            [
                "issue",
                "view",
                str(number),
                "--repo",
                f"{owner}/{repo}",
                "--json",
                ",".join(self.ISSUE_FIELDS),
            ]
        )
        if not isinstance(payload, dict):
            raise GitHubTrackerServiceError(502, "GitHub CLI returned an unexpected issue payload.")
        return self._normalize_issue_detail(payload)

    def add_comment(
        self,
        owner: str,
        repo: str,
        number: int,
        payload: GitHubIssueCommentCreate,
    ) -> GitHubIssueDetailRead:
        """Add a comment through gh and return the refreshed issue view."""
        self._run(
            [
                "issue",
                "comment",
                str(number),
                "--repo",
                f"{owner}/{repo}",
                "--body",
                payload.body.strip(),
            ]
        )
        return self.get_issue(owner=owner, repo=repo, number=number)

    def add_labels(
        self,
        owner: str,
        repo: str,
        number: int,
        payload: GitHubIssueLabelsUpdate,
    ) -> GitHubIssueDetailRead:
        """Add labels through gh and return the refreshed issue view."""
        normalized = [label.strip() for label in payload.labels if label.strip()]
        if not normalized:
            raise GitHubTrackerServiceError(422, "At least one non-empty label is required.")

        self._run(
            [
                "issue",
                "edit",
                str(number),
                "--repo",
                f"{owner}/{repo}",
                "--add-label",
                ",".join(normalized),
            ]
        )
        return self.get_issue(owner=owner, repo=repo, number=number)

    def remove_label(
        self,
        owner: str,
        repo: str,
        number: int,
        label: str,
    ) -> GitHubIssueDetailRead:
        """Remove a label through gh and return the refreshed issue view."""
        normalized = label.strip()
        if not normalized:
            raise GitHubTrackerServiceError(422, "Label name must not be empty.")

        self._run(
            [
                "issue",
                "edit",
                str(number),
                "--repo",
                f"{owner}/{repo}",
                "--remove-label",
                normalized,
            ]
        )
        return self.get_issue(owner=owner, repo=repo, number=number)

    def _run_json(self, args: list[str]) -> dict[str, object] | list[object]:
        """Run a gh command and decode its JSON output."""
        completed = self._run(args)

        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise GitHubTrackerServiceError(
                502,
                "GitHub CLI returned invalid JSON output.",
            ) from exc

    def _run(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        """Run a gh command and normalize execution errors."""
        try:
            completed = subprocess.run(
                ["gh", *args],
                capture_output=True,
                check=False,
                text=True,
                timeout=15.0,
            )
        except FileNotFoundError as exc:
            raise GitHubTrackerServiceError(
                503,
                "GitHub CLI is not installed on the host. Install `gh` and run diagnostics again.",
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise GitHubTrackerServiceError(
                504,
                "GitHub CLI timed out while talking to GitHub. "
                "Check network connectivity and gh auth.",
            ) from exc
        except OSError as exc:
            raise GitHubTrackerServiceError(503, f"Failed to launch GitHub CLI: {exc}") from exc

        if completed.returncode != 0:
            detail = self._normalize_error_detail(completed.stderr, completed.stdout)
            raise GitHubTrackerServiceError(self._status_code_for_error(detail), detail)
        return completed

    @staticmethod
    def _normalize_repo(payload: dict[str, object]) -> GitHubRepoRead:
        """Convert gh repo JSON into the normalized API schema."""
        owner = payload.get("owner") if isinstance(payload.get("owner"), dict) else {}
        default_branch = payload.get("defaultBranchRef")
        return GitHubRepoRead(
            owner=str(owner.get("login") or ""),
            name=str(payload.get("name") or ""),
            full_name=str(payload.get("nameWithOwner") or ""),
            description=_optional_string(payload.get("description")),
            url=str(payload.get("url") or ""),
            ssh_url=_optional_string(payload.get("sshUrl")),
            is_private=bool(payload.get("isPrivate")),
            visibility=_optional_string(payload.get("visibility")),
            default_branch=_extract_default_branch(default_branch),
            has_issues_enabled=bool(payload.get("hasIssuesEnabled", True)),
            viewer_permission=_optional_string(payload.get("viewerPermission")),
            updated_at=_optional_string(payload.get("updatedAt")),
            pushed_at=_optional_string(payload.get("pushedAt")),
        )

    @staticmethod
    def _normalize_issue(payload: dict[str, object]) -> GitHubIssueRead:
        """Convert gh issue JSON into the normalized API schema."""
        author = payload.get("author") if isinstance(payload.get("author"), dict) else {}
        labels = payload.get("labels") if isinstance(payload.get("labels"), list) else []
        comments = payload.get("comments")

        return GitHubIssueRead(
            number=int(payload.get("number") or 0),
            title=str(payload.get("title") or ""),
            body=_optional_string(payload.get("body")),
            state=str(payload.get("state") or ""),
            url=str(payload.get("url") or ""),
            author_login=_optional_string(author.get("login")),
            labels=[
                str(item.get("name"))
                for item in labels
                if isinstance(item, dict) and item.get("name")
            ],
            comments_count=_extract_comments_count(comments),
            created_at=_optional_string(payload.get("createdAt")),
            updated_at=_optional_string(payload.get("updatedAt")),
        )

    @staticmethod
    def _normalize_branch(
        payload: dict[str, object],
        *,
        default_branch: str | None,
    ) -> GitHubBranchRead:
        """Convert gh branch JSON into the normalized API schema."""
        name = _optional_string(payload.get("name"))
        if name is None:
            raise GitHubTrackerServiceError(502, "GitHub CLI returned a branch without a name.")

        return GitHubBranchRead(
            name=name,
            is_default=name == default_branch,
            is_protected=bool(payload.get("protected", False)),
        )

    @staticmethod
    def _normalize_issue_detail(payload: dict[str, object]) -> GitHubIssueDetailRead:
        """Convert gh issue JSON into the full issue detail schema."""
        summary = GitHubTrackerService._normalize_issue(payload)
        comments = payload.get("comments") if isinstance(payload.get("comments"), list) else []
        return GitHubIssueDetailRead(
            **summary.model_dump(),
            comments=[
                _normalize_issue_comment(item)
                for item in comments
                if isinstance(item, dict) and isinstance(item.get("body"), str)
            ],
        )

    @staticmethod
    def _status_code_for_error(detail: str) -> int:
        """Map gh failures to useful HTTP status codes."""
        normalized = detail.lower()
        if "could not resolve to a repository" in normalized or "not found" in normalized:
            return 404
        if "could not resolve to an issue" in normalized or "issue not found" in normalized:
            return 404
        if (
            "not logged into any github hosts" in normalized
            or "authentication failed" in normalized
        ):
            return 503
        if "http 401" in normalized or "http 403" in normalized:
            return 503
        return 502

    @staticmethod
    def _normalize_error_detail(stderr: str, stdout: str) -> str:
        """Prefer actionable stderr details from gh."""
        detail = (stderr or stdout).strip()
        if detail:
            return detail
        return "GitHub CLI request failed. Run diagnostics and verify `gh auth status`."



def _extract_default_branch(value: object) -> str | None:
    """Extract default branch name from gh repo payload."""
    if isinstance(value, dict):
        return _optional_string(value.get("name"))
    return None



def _extract_comments_count(value: object) -> int:
    """Extract a stable comment count from gh issue payloads."""
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        total = value.get("totalCount")
        if isinstance(total, int):
            return total
    if isinstance(value, int):
        return value
    return 0



def _optional_string(value: object) -> str | None:
    """Return a string value when present and non-empty."""
    if isinstance(value, str) and value:
        return value
    return None


def _normalize_issue_comment(payload: dict[str, object]) -> GitHubIssueCommentRead:
    """Convert gh issue comment JSON into the normalized API schema."""
    author = payload.get("author") if isinstance(payload.get("author"), dict) else {}
    return GitHubIssueCommentRead(
        id=_optional_string(payload.get("id")),
        author_login=_optional_string(author.get("login")),
        body=str(payload.get("body") or ""),
        url=_optional_string(payload.get("url")),
        created_at=_optional_string(payload.get("createdAt")),
        updated_at=_optional_string(payload.get("updatedAt")),
    )
