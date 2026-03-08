"""Proxy GitHub tracker requests to the host executor bridge."""

from __future__ import annotations

import json
from typing import Any, TypeVar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from app.core.config import Settings
from app.schemas.github import (
    GitHubIssueCommentCreate,
    GitHubIssueDetailRead,
    GitHubIssueLabelsUpdate,
    GitHubIssueListResponse,
    GitHubIssueRead,
    GitHubPullChecksResponse,
    GitHubPullListResponse,
    GitHubPullRead,
    GitHubRepoListResponse,
    GitHubRepoRead,
)

SchemaModel = TypeVar(
    "SchemaModel",
    GitHubRepoRead,
    GitHubRepoListResponse,
    GitHubIssueRead,
    GitHubIssueListResponse,
    GitHubIssueDetailRead,
    GitHubPullRead,
    GitHubPullListResponse,
    GitHubPullChecksResponse,
)


class GitHubProxyServiceError(Exception):
    """Normalized host-executor proxy error."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class GitHubProxyService:
    """Read GitHub repo and issue data from the configured host executor."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def list_repos(
        self,
        owner: str | None,
        limit: int,
        query: str | None,
    ) -> GitHubRepoListResponse:
        """Return repositories from the host executor bridge."""
        params: dict[str, str] = {"limit": str(limit)}
        if owner:
            params["owner"] = owner
        if query:
            params["q"] = query

        data = self._request_json("github/repos", params)
        return self._validate(data, GitHubRepoListResponse, "repository list")

    def get_repo(self, owner: str, repo: str) -> GitHubRepoRead:
        """Return one repository from the host executor bridge."""
        data = self._request_json(f"github/repos/{owner}/{repo}")
        return self._validate(data, GitHubRepoRead, "repository")

    def list_issues(
        self,
        owner: str,
        repo: str,
        state: str,
        limit: int,
    ) -> GitHubIssueListResponse:
        """Return repository issues from the host executor bridge."""
        data = self._request_json(
            f"github/repos/{owner}/{repo}/issues",
            {"state": state, "limit": str(limit)},
        )
        return self._validate(data, GitHubIssueListResponse, "issue list")

    def get_issue(self, owner: str, repo: str, number: int) -> GitHubIssueDetailRead:
        """Return one repository issue from the host executor bridge."""
        data = self._request_json(f"github/repos/{owner}/{repo}/issues/{number}")
        return self._validate(data, GitHubIssueDetailRead, "issue")

    def list_pulls(
        self,
        owner: str,
        repo: str,
        state: str,
        limit: int,
    ) -> GitHubPullListResponse:
        """Return repository pull requests from the host executor bridge."""
        data = self._request_json(
            f"github/repos/{owner}/{repo}/pulls",
            {"state": state, "limit": str(limit)},
        )
        return self._validate(data, GitHubPullListResponse, "pull request list")

    def get_pull(self, owner: str, repo: str, number: int) -> GitHubPullRead:
        """Return one repository pull request from the host executor bridge."""
        data = self._request_json(f"github/repos/{owner}/{repo}/pulls/{number}")
        return self._validate(data, GitHubPullRead, "pull request")

    def get_pull_checks(self, owner: str, repo: str, number: int) -> GitHubPullChecksResponse:
        """Return one repository pull request checks payload from the host executor bridge."""
        data = self._request_json(f"github/repos/{owner}/{repo}/pulls/{number}/checks")
        return self._validate(data, GitHubPullChecksResponse, "pull request checks")

    def add_comment(
        self,
        owner: str,
        repo: str,
        number: int,
        payload: GitHubIssueCommentCreate,
    ) -> GitHubIssueDetailRead:
        """Add a comment to an issue through the host executor bridge."""
        data = self._request_json(
            f"github/repos/{owner}/{repo}/issues/{number}/comments",
            method="POST",
            body=payload.model_dump(),
        )
        return self._validate(data, GitHubIssueDetailRead, "issue")

    def add_labels(
        self,
        owner: str,
        repo: str,
        number: int,
        payload: GitHubIssueLabelsUpdate,
    ) -> GitHubIssueDetailRead:
        """Add labels to an issue through the host executor bridge."""
        data = self._request_json(
            f"github/repos/{owner}/{repo}/issues/{number}/labels",
            method="POST",
            body=payload.model_dump(),
        )
        return self._validate(data, GitHubIssueDetailRead, "issue")

    def remove_label(
        self,
        owner: str,
        repo: str,
        number: int,
        label_name: str,
    ) -> GitHubIssueDetailRead:
        """Remove a label from an issue through the host executor bridge."""
        data = self._request_json(
            f"github/repos/{owner}/{repo}/issues/{number}/labels/{label_name}",
            method="DELETE",
        )
        return self._validate(data, GitHubIssueDetailRead, "issue")

    def _request_json(
        self,
        path: str,
        params: dict[str, str] | None = None,
        *,
        method: str = "GET",
        body: dict[str, object] | None = None,
    ) -> Any:
        """Request JSON from the host executor bridge."""
        base_url = self._normalize_base_url(self.settings.host_executor_base_url)
        if base_url is None:
            raise GitHubProxyServiceError(
                503,
                "Host executor is not configured. Start it locally and set HOST_EXECUTOR_BASE_URL.",
            )

        query = f"?{urlencode(params)}" if params else ""
        url = urljoin(f"{base_url}/", path) + query
        payload = None
        headers = {"Accept": "application/json"}
        if body is not None:
            payload = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(url, headers=headers, data=payload, method=method)

        try:
            with urlopen(
                request,
                timeout=self.settings.host_executor_api_timeout_seconds,
            ) as response:
                response_payload = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = self._extract_error_detail(exc)
            raise GitHubProxyServiceError(exc.code, detail) from exc
        except URLError as exc:
            raise GitHubProxyServiceError(
                503,
                f"Host executor is unreachable: {exc.reason}.",
            ) from exc
        except OSError as exc:
            raise GitHubProxyServiceError(503, f"Host executor request failed: {exc}") from exc

        try:
            return json.loads(response_payload)
        except json.JSONDecodeError as exc:
            raise GitHubProxyServiceError(502, "Host executor returned invalid JSON.") from exc

    @staticmethod
    def _validate(data: Any, schema: type[SchemaModel], label: str) -> SchemaModel:
        """Validate JSON payload from the host executor against the expected schema."""
        try:
            return schema.model_validate(data)
        except Exception as exc:  # noqa: BLE001
            raise GitHubProxyServiceError(
                502,
                f"Host executor returned an unexpected {label} payload.",
            ) from exc

    @staticmethod
    def _extract_error_detail(error: HTTPError) -> str:
        """Extract JSON detail from a failed host executor response when available."""
        try:
            payload = error.read().decode("utf-8")
        except Exception:  # noqa: BLE001
            payload = ""

        if payload:
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                data = None
            if isinstance(data, dict) and isinstance(data.get("detail"), str) and data["detail"]:
                return data["detail"]
            return payload.strip() or f"Host executor returned HTTP {error.code}."

        return f"Host executor returned HTTP {error.code}."

    @staticmethod
    def _normalize_base_url(value: str | None) -> str | None:
        """Normalize optional base URL configuration."""
        if value is None:
            return None
        normalized = value.strip().rstrip("/")
        return normalized or None
