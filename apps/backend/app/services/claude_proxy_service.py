"""Proxy Claude Code session requests to the host executor bridge."""

from __future__ import annotations

import json
from typing import Any, TypeVar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from app.core.config import Settings
from app.schemas.claude import ClaudeSessionEventsResponse, ClaudeSessionRead, ClaudeSessionStart

SchemaModel = TypeVar("SchemaModel", ClaudeSessionRead, ClaudeSessionEventsResponse)


class ClaudeProxyServiceError(Exception):
    """Normalized host-executor proxy error for Claude session requests."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class ClaudeProxyService:
    """Read and mutate Claude sessions through the host executor."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def start_session(self, payload: ClaudeSessionStart) -> ClaudeSessionRead:
        """Start a new host-side Claude session."""
        data = self._request_json(
            "claude/sessions/start",
            method="POST",
            body=payload.model_dump(),
        )
        return self._validate(data, ClaudeSessionRead, "Claude session")

    def get_session(self, run_id: str) -> ClaudeSessionRead:
        """Return one host-side Claude session."""
        data = self._request_json(f"claude/sessions/{run_id}")
        return self._validate(data, ClaudeSessionRead, "Claude session")

    def get_events(self, run_id: str, *, offset: int) -> ClaudeSessionEventsResponse:
        """Return incremental host-side Claude terminal output."""
        data = self._request_json(f"claude/sessions/{run_id}/events", params={"offset": str(offset)})
        return self._validate(data, ClaudeSessionEventsResponse, "Claude session events")

    def cancel_session(self, run_id: str) -> ClaudeSessionRead:
        """Cancel one host-side Claude session."""
        data = self._request_json(f"claude/sessions/{run_id}/cancel", method="POST")
        return self._validate(data, ClaudeSessionRead, "Claude session")

    def resume_session(self, run_id: str) -> ClaudeSessionRead:
        """Resume one interrupted host-side Claude session."""
        data = self._request_json(f"claude/sessions/{run_id}/resume", method="POST")
        return self._validate(data, ClaudeSessionRead, "Claude session")

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
            raise ClaudeProxyServiceError(
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
            raise ClaudeProxyServiceError(exc.code, detail) from exc
        except URLError as exc:
            raise ClaudeProxyServiceError(
                503,
                f"Host executor is unreachable: {exc.reason}.",
            ) from exc
        except OSError as exc:
            raise ClaudeProxyServiceError(503, f"Host executor request failed: {exc}") from exc

        try:
            return json.loads(response_payload)
        except json.JSONDecodeError as exc:
            raise ClaudeProxyServiceError(502, "Host executor returned invalid JSON.") from exc

    @staticmethod
    def _validate(data: Any, schema: type[SchemaModel], label: str) -> SchemaModel:
        """Validate JSON payload from the host executor against the expected schema."""
        try:
            return schema.model_validate(data)
        except Exception as exc:  # noqa: BLE001
            raise ClaudeProxyServiceError(
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
