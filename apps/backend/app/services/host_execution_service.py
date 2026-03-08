"""Coordinator for host-executor diagnostics and readiness."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from app.core.config import Settings
from app.schemas.host import (
    HostDiagnosticsResponse,
    HostExecutionReadinessResponse,
    HostExecutionSource,
)


class HostExecutionReadinessServiceError(Exception):
    """Raised when the host executor bridge cannot provide diagnostics."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class HostExecutionReadinessService:
    """Expose host-only diagnostics and readiness for the execution bridge."""

    def __init__(
        self,
        settings: Settings,
    ) -> None:
        self.settings = settings

    def build_readiness(self) -> HostExecutionReadinessResponse:
        """Build readiness for the host executor bridge only."""
        host_executor_url = self._normalize_base_url(self.settings.host_executor_base_url)

        if host_executor_url is None:
            return HostExecutionReadinessResponse(
                generated_at=datetime.now(UTC),
                execution_source=HostExecutionSource.HOST_EXECUTOR,
                effective_ready=False,
                host_executor_url=None,
                host_executor_reachable=False,
                host_executor_error=(
                    "Host executor is not configured. Start it locally and set "
                    "HOST_EXECUTOR_BASE_URL."
                ),
                host_executor=None,
            )

        host_executor_snapshot, error_message = self._fetch_host_executor_snapshot(
            host_executor_url
        )
        if host_executor_snapshot is None:
            return HostExecutionReadinessResponse(
                generated_at=datetime.now(UTC),
                execution_source=HostExecutionSource.HOST_EXECUTOR,
                effective_ready=False,
                host_executor_url=host_executor_url,
                host_executor_reachable=False,
                host_executor_error=error_message,
                host_executor=None,
            )

        return HostExecutionReadinessResponse(
            generated_at=datetime.now(UTC),
            execution_source=HostExecutionSource.HOST_EXECUTOR,
            effective_ready=host_executor_snapshot.ready,
            host_executor_url=host_executor_url,
            host_executor_reachable=True,
            host_executor_error=None,
            host_executor=host_executor_snapshot,
        )

    def get_host_diagnostics(self) -> HostDiagnosticsResponse:
        """Return a live host-executor diagnostics snapshot or raise a normalized error."""
        host_executor_url = self._normalize_base_url(self.settings.host_executor_base_url)
        if host_executor_url is None:
            raise HostExecutionReadinessServiceError(
                "Host executor is not configured. Start it locally and set "
                "HOST_EXECUTOR_BASE_URL."
            )

        host_executor_snapshot, error_message = self._fetch_host_executor_snapshot(
            host_executor_url
        )
        if host_executor_snapshot is None:
            raise HostExecutionReadinessServiceError(
                error_message or "Host executor diagnostics are unavailable."
            )
        return host_executor_snapshot

    def _fetch_host_executor_snapshot(
        self,
        base_url: str,
    ) -> tuple[HostDiagnosticsResponse | None, str | None]:
        """Fetch diagnostics from the host executor over HTTP."""
        url = urljoin(f"{base_url}/", "diagnostics")
        request = Request(url, headers={"Accept": "application/json"})

        try:
            with urlopen(request, timeout=self.settings.host_executor_timeout_seconds) as response:
                payload = response.read().decode("utf-8")
        except HTTPError as exc:
            return None, f"Host executor returned HTTP {exc.code}."
        except URLError as exc:
            return None, f"Host executor is unreachable: {exc.reason}."
        except OSError as exc:
            return None, f"Host executor request failed: {exc}."

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return None, "Host executor returned invalid JSON."

        try:
            snapshot = HostDiagnosticsResponse.model_validate(data)
        except Exception:
            return None, "Host executor returned an unexpected diagnostics payload."

        return snapshot, None

    @staticmethod
    def _normalize_base_url(value: str | None) -> str | None:
        """Normalize optional base URL configuration."""
        if value is None:
            return None
        normalized = value.strip().rstrip("/")
        return normalized or None
