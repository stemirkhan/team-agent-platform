"""Proxy workspace lifecycle requests to the host executor bridge."""

from __future__ import annotations

import json
from typing import Any, TypeVar
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from app.core.config import Settings
from app.schemas.workspace import (
    WorkspaceCommandsRun,
    WorkspaceCommandsRunResponse,
    WorkspaceCommit,
    WorkspaceExecutionConfigRead,
    WorkspaceListResponse,
    WorkspaceMaterialize,
    WorkspacePrepare,
    WorkspacePullRequestCreate,
    WorkspaceRead,
)

SchemaModel = TypeVar(
    "SchemaModel",
    WorkspaceRead,
    WorkspaceListResponse,
    WorkspaceExecutionConfigRead,
    WorkspaceCommandsRunResponse,
)


class WorkspaceProxyServiceError(Exception):
    """Normalized host-executor proxy error for workspace lifecycle requests."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class WorkspaceProxyService:
    """Read and mutate workspace state through the configured host executor."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def list_workspaces(self) -> WorkspaceListResponse:
        """Return all workspaces from the host executor bridge."""
        data = self._request_json("workspaces")
        return self._validate(data, WorkspaceListResponse, "workspace list")

    def prepare_workspace(self, payload: WorkspacePrepare) -> WorkspaceRead:
        """Prepare a new workspace through the host executor bridge."""
        data = self._request_json("workspaces/prepare", method="POST", body=payload.model_dump())
        return self._validate(data, WorkspaceRead, "workspace")

    def get_workspace(self, workspace_id: str) -> WorkspaceRead:
        """Return one workspace from the host executor bridge."""
        data = self._request_json(f"workspaces/{workspace_id}")
        return self._validate(data, WorkspaceRead, "workspace")

    def get_execution_config(self, workspace_id: str) -> WorkspaceExecutionConfigRead:
        """Return repo-level execution config from the host executor bridge."""
        data = self._request_json(f"workspaces/{workspace_id}/execution-config")
        return self._validate(data, WorkspaceExecutionConfigRead, "workspace execution config")

    def commit_workspace(self, workspace_id: str, payload: WorkspaceCommit) -> WorkspaceRead:
        """Commit a workspace through the host executor bridge."""
        data = self._request_json(
            f"workspaces/{workspace_id}/commit",
            method="POST",
            body=payload.model_dump(),
        )
        return self._validate(data, WorkspaceRead, "workspace")

    def materialize_workspace(
        self,
        workspace_id: str,
        payload: WorkspaceMaterialize,
    ) -> WorkspaceRead:
        """Write text files into a workspace through the host executor bridge."""
        data = self._request_json(
            f"workspaces/{workspace_id}/materialize",
            method="POST",
            body=payload.model_dump(),
        )
        return self._validate(data, WorkspaceRead, "workspace")

    def cleanup_workspace(self, workspace_id: str) -> WorkspaceRead:
        """Restore or delete temporary run scaffolding inside a workspace."""
        data = self._request_json(f"workspaces/{workspace_id}/cleanup", method="POST")
        return self._validate(data, WorkspaceRead, "workspace")

    def run_commands(
        self,
        workspace_id: str,
        payload: WorkspaceCommandsRun,
    ) -> WorkspaceCommandsRunResponse:
        """Run sequential shell commands inside one workspace through the host executor."""
        data = self._request_json(
            f"workspaces/{workspace_id}/commands",
            method="POST",
            body=payload.model_dump(),
        )
        return self._validate(data, WorkspaceCommandsRunResponse, "workspace command execution")

    def push_workspace(self, workspace_id: str) -> WorkspaceRead:
        """Push a workspace through the host executor bridge."""
        data = self._request_json(f"workspaces/{workspace_id}/push", method="POST")
        return self._validate(data, WorkspaceRead, "workspace")

    def create_pull_request(
        self,
        workspace_id: str,
        payload: WorkspacePullRequestCreate,
    ) -> WorkspaceRead:
        """Create a pull request through the host executor bridge."""
        data = self._request_json(
            f"workspaces/{workspace_id}/pull-request",
            method="POST",
            body=payload.model_dump(),
        )
        return self._validate(data, WorkspaceRead, "workspace")

    def delete_workspace(self, workspace_id: str) -> None:
        """Delete a workspace through the host executor bridge."""
        self._request_json(f"workspaces/{workspace_id}", method="DELETE", expect_json=False)

    def _request_json(
        self,
        path: str,
        *,
        method: str = "GET",
        body: dict[str, object] | None = None,
        expect_json: bool = True,
    ) -> Any:
        """Request JSON from the host executor bridge."""
        base_url = self._normalize_base_url(self.settings.host_executor_base_url)
        if base_url is None:
            raise WorkspaceProxyServiceError(
                503,
                "Host executor is not configured. Start it locally and set HOST_EXECUTOR_BASE_URL.",
            )

        url = urljoin(f"{base_url}/", path)
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
            raise WorkspaceProxyServiceError(exc.code, detail) from exc
        except URLError as exc:
            raise WorkspaceProxyServiceError(
                503,
                f"Host executor is unreachable: {exc.reason}.",
            ) from exc
        except OSError as exc:
            raise WorkspaceProxyServiceError(503, f"Host executor request failed: {exc}") from exc

        if not expect_json:
            return None

        try:
            return json.loads(response_payload)
        except json.JSONDecodeError as exc:
            raise WorkspaceProxyServiceError(502, "Host executor returned invalid JSON.") from exc

    @staticmethod
    def _validate(data: Any, schema: type[SchemaModel], label: str) -> SchemaModel:
        """Validate JSON payload from the host executor against the expected schema."""
        try:
            return schema.model_validate(data)
        except Exception as exc:  # noqa: BLE001
            raise WorkspaceProxyServiceError(
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
