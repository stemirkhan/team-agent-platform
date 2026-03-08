"""GitHub SCM adapter backed by host git/gh CLI tooling."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

from host_executor_app.schemas.github import (
    GitHubPullCheckRead,
    GitHubPullChecksResponse,
    GitHubPullChecksSummary,
    GitHubPullListResponse,
    GitHubPullRead,
)


@dataclass(slots=True)
class GitHubScmServiceError(Exception):
    """Normalized error raised when gh PR commands fail."""

    status_code: int
    detail: str


class GitHubScmService:
    """Provide normalized pull request reads through the GitHub CLI."""

    PULL_FIELDS = [
        "author",
        "baseRefName",
        "body",
        "comments",
        "createdAt",
        "headRefName",
        "isDraft",
        "labels",
        "mergeStateStatus",
        "mergeable",
        "number",
        "reviewDecision",
        "state",
        "title",
        "updatedAt",
        "url",
    ]
    CHECK_FIELDS = [
        "bucket",
        "completedAt",
        "description",
        "event",
        "link",
        "name",
        "startedAt",
        "state",
        "workflow",
    ]

    def list_pulls(
        self,
        owner: str,
        repo: str,
        state: str,
        limit: int,
    ) -> GitHubPullListResponse:
        """Return normalized pull requests for a repository."""
        payload = self._run_json(
            [
                "pr",
                "list",
                "--repo",
                f"{owner}/{repo}",
                "--state",
                state,
                "--limit",
                str(limit),
                "--json",
                ",".join(self.PULL_FIELDS),
            ]
        )
        if not isinstance(payload, list):
            raise GitHubScmServiceError(502, "GitHub CLI returned an unexpected pull request list.")

        items = [self._normalize_pull(item) for item in payload if isinstance(item, dict)]
        return GitHubPullListResponse(items=items, total=len(items), limit=limit, state=state)

    def get_pull(self, owner: str, repo: str, number: int) -> GitHubPullRead:
        """Return normalized pull request details for one PR."""
        payload = self._run_json(
            [
                "pr",
                "view",
                str(number),
                "--repo",
                f"{owner}/{repo}",
                "--json",
                ",".join(self.PULL_FIELDS),
            ]
        )
        if not isinstance(payload, dict):
            raise GitHubScmServiceError(
                502,
                "GitHub CLI returned an unexpected pull request payload.",
            )
        return self._normalize_pull(payload)

    def get_pull_checks(self, owner: str, repo: str, number: int) -> GitHubPullChecksResponse:
        """Return normalized PR checks for one pull request."""
        try:
            payload = self._run_json(
                [
                    "pr",
                    "checks",
                    str(number),
                    "--repo",
                    f"{owner}/{repo}",
                    "--json",
                    ",".join(self.CHECK_FIELDS),
                ],
                allowed_returncodes=(0, 8),
            )
        except GitHubScmServiceError as exc:
            if "no checks reported on the pull request" in exc.detail.lower():
                return GitHubPullChecksResponse(items=[], total=0)
            raise

        if not isinstance(payload, list):
            raise GitHubScmServiceError(
                502,
                "GitHub CLI returned an unexpected pull request checks payload.",
            )

        items = [self._normalize_check(item) for item in payload if isinstance(item, dict)]
        summary = GitHubPullChecksSummary(
            pass_count=sum(1 for item in items if item.bucket == "pass"),
            fail_count=sum(1 for item in items if item.bucket == "fail"),
            pending_count=sum(1 for item in items if item.bucket == "pending"),
            skipping_count=sum(1 for item in items if item.bucket == "skipping"),
            cancel_count=sum(1 for item in items if item.bucket == "cancel"),
        )
        return GitHubPullChecksResponse(items=items, total=len(items), summary=summary)

    def _run_json(
        self,
        args: list[str],
        *,
        allowed_returncodes: tuple[int, ...] = (0,),
    ) -> dict[str, object] | list[object]:
        """Run a gh command and decode its JSON output."""
        completed = self._run(args, allowed_returncodes=allowed_returncodes)

        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise GitHubScmServiceError(502, "GitHub CLI returned invalid JSON output.") from exc

    def _run(
        self,
        args: list[str],
        *,
        allowed_returncodes: tuple[int, ...] = (0,),
    ) -> subprocess.CompletedProcess[str]:
        """Run a gh command and normalize execution errors."""
        try:
            completed = subprocess.run(
                ["gh", *args],
                capture_output=True,
                check=False,
                text=True,
                timeout=20.0,
            )
        except FileNotFoundError as exc:
            raise GitHubScmServiceError(
                503,
                "GitHub CLI is not installed on the host. Install `gh` and run diagnostics again.",
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise GitHubScmServiceError(
                504,
                "GitHub CLI timed out while talking to GitHub. "
                "Check network connectivity and gh auth.",
            ) from exc
        except OSError as exc:
            raise GitHubScmServiceError(503, f"Failed to launch GitHub CLI: {exc}") from exc

        if completed.returncode not in allowed_returncodes:
            detail = self._normalize_error_detail(completed.stderr, completed.stdout)
            raise GitHubScmServiceError(self._status_code_for_error(detail), detail)
        return completed

    @staticmethod
    def _normalize_pull(payload: dict[str, object]) -> GitHubPullRead:
        """Convert gh PR JSON into the normalized API schema."""
        author = payload.get("author") if isinstance(payload.get("author"), dict) else {}
        labels = payload.get("labels") if isinstance(payload.get("labels"), list) else []
        comments = payload.get("comments")

        return GitHubPullRead(
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
            is_draft=bool(payload.get("isDraft")),
            base_ref_name=_optional_string(payload.get("baseRefName")),
            head_ref_name=_optional_string(payload.get("headRefName")),
            merge_state_status=_optional_string(payload.get("mergeStateStatus")),
            mergeable=_optional_string(payload.get("mergeable")),
            review_decision=_optional_string(payload.get("reviewDecision")),
            created_at=_optional_string(payload.get("createdAt")),
            updated_at=_optional_string(payload.get("updatedAt")),
        )

    @staticmethod
    def _normalize_check(payload: dict[str, object]) -> GitHubPullCheckRead:
        """Convert gh PR checks JSON into the normalized API schema."""
        return GitHubPullCheckRead(
            name=str(payload.get("name") or ""),
            state=str(payload.get("state") or ""),
            bucket=_optional_string(payload.get("bucket")),
            workflow=_optional_string(payload.get("workflow")),
            description=_optional_string(payload.get("description")),
            event=_optional_string(payload.get("event")),
            link=_optional_string(payload.get("link")),
            started_at=_optional_string(payload.get("startedAt")),
            completed_at=_optional_string(payload.get("completedAt")),
        )

    @staticmethod
    def _status_code_for_error(detail: str) -> int:
        """Map gh failures to useful HTTP status codes."""
        normalized = detail.lower()
        if "could not resolve to a repository" in normalized or "not found" in normalized:
            return 404
        if (
            "could not resolve to a pullrequest" in normalized
            or "pull request not found" in normalized
        ):
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


def _extract_comments_count(value: object) -> int:
    """Extract a stable comment count from gh PR payloads."""
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
