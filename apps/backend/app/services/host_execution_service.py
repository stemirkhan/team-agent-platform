"""Coordinator for host-executor diagnostics and readiness."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from app.core.config import Settings
from app.models.export_job import RuntimeTarget
from app.schemas.host import (
    HostDiagnosticsResponse,
    HostExecutionReadinessResponse,
    HostExecutionSource,
    HostToolStatus,
)
from app.services.host_executor_client import (
    build_host_executor_headers,
    normalize_host_executor_base_url,
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

    def build_readiness(
        self,
        *,
        runtime_target: str | None = None,
        force_refresh: bool = False,
    ) -> HostExecutionReadinessResponse:
        """Build readiness for the host executor bridge only."""
        host_executor_url = self._normalize_base_url(self.settings.host_executor_base_url)

        if host_executor_url is None:
            return HostExecutionReadinessResponse(
                generated_at=datetime.now(UTC),
                execution_source=HostExecutionSource.HOST_EXECUTOR,
                effective_ready=False,
                requested_runtime=RuntimeTarget(runtime_target) if runtime_target else None,
                runtime_ready={},
                host_executor_url=None,
                host_executor_reachable=False,
                host_executor_error=(
                    "Host executor is not configured. Start it locally and set "
                    "HOST_EXECUTOR_BASE_URL."
                ),
                host_executor=None,
            )

        host_executor_snapshot, error_message = self._fetch_host_executor_snapshot(
            host_executor_url,
            force_refresh=force_refresh,
        )
        if host_executor_snapshot is None:
            return HostExecutionReadinessResponse(
                generated_at=datetime.now(UTC),
                execution_source=HostExecutionSource.HOST_EXECUTOR,
                effective_ready=False,
                requested_runtime=RuntimeTarget(runtime_target) if runtime_target else None,
                runtime_ready={},
                host_executor_url=host_executor_url,
                host_executor_reachable=False,
                host_executor_error=error_message,
                host_executor=None,
            )

        runtime_ready = self._build_runtime_ready_map(host_executor_snapshot)
        effective_ready = (
            runtime_ready.get(runtime_target, False)
            if runtime_target is not None
            else any(runtime_ready.values())
        )

        return HostExecutionReadinessResponse(
            generated_at=datetime.now(UTC),
            execution_source=HostExecutionSource.HOST_EXECUTOR,
            effective_ready=effective_ready,
            requested_runtime=RuntimeTarget(runtime_target) if runtime_target else None,
            runtime_ready=runtime_ready,
            host_executor_url=host_executor_url,
            host_executor_reachable=True,
            host_executor_error=None,
            host_executor=host_executor_snapshot,
        )

    def get_host_diagnostics(self, *, force_refresh: bool = False) -> HostDiagnosticsResponse:
        """Return a live host-executor diagnostics snapshot or raise a normalized error."""
        host_executor_url = self._normalize_base_url(self.settings.host_executor_base_url)
        if host_executor_url is None:
            raise HostExecutionReadinessServiceError(
                "Host executor is not configured. Start it locally and set "
                "HOST_EXECUTOR_BASE_URL."
            )

        host_executor_snapshot, error_message = self._fetch_host_executor_snapshot(
            host_executor_url,
            force_refresh=force_refresh,
        )
        if host_executor_snapshot is None:
            raise HostExecutionReadinessServiceError(
                error_message or "Host executor diagnostics are unavailable."
            )
        return host_executor_snapshot

    def _fetch_host_executor_snapshot(
        self,
        base_url: str,
        *,
        force_refresh: bool = False,
    ) -> tuple[HostDiagnosticsResponse | None, str | None]:
        """Fetch diagnostics from the host executor over HTTP."""
        max_attempts = 2
        last_error: str | None = None

        for attempt in range(max_attempts):
            snapshot, error_message = self._fetch_host_executor_snapshot_once(
                base_url,
                force_refresh=force_refresh,
            )
            if snapshot is not None:
                return snapshot, None

            last_error = error_message
            if attempt + 1 >= max_attempts or not self._is_retryable_snapshot_error(error_message):
                break
            time.sleep(0.2)

        return None, last_error

    def _fetch_host_executor_snapshot_once(
        self,
        base_url: str,
        *,
        force_refresh: bool = False,
    ) -> tuple[HostDiagnosticsResponse | None, str | None]:
        """Fetch one diagnostics snapshot attempt from the host executor."""
        path = "diagnostics/refresh" if force_refresh else "diagnostics"
        url = urljoin(f"{base_url}/", path)
        request_kwargs: dict[str, object] = {"headers": build_host_executor_headers(self.settings)}
        if force_refresh:
            request_kwargs["data"] = b"{}"
            request_kwargs["method"] = "POST"
        request = Request(url, **request_kwargs)

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
    def _is_retryable_snapshot_error(error_message: str | None) -> bool:
        """Return whether one diagnostics fetch error is likely transient."""
        if not error_message:
            return False

        normalized = error_message.lower()
        if normalized.startswith("host executor is unreachable:"):
            return True
        if normalized.startswith("host executor request failed:"):
            return True
        if normalized.startswith("host executor returned http "):
            try:
                code = int(normalized.removeprefix("host executor returned http ").split(".", 1)[0])
            except ValueError:
                return False
            return code >= 500
        return False

    @staticmethod
    def _normalize_base_url(value: str | None) -> str | None:
        """Normalize optional base URL configuration."""
        return normalize_host_executor_base_url(value)

    @staticmethod
    def _build_runtime_ready_map(snapshot: HostDiagnosticsResponse) -> dict[str, bool]:
        """Return runtime-specific readiness from the diagnostics snapshot."""
        core_ready = snapshot.pty_supported and all(
            tool.status == HostToolStatus.READY for tool in (snapshot.tools.git, snapshot.tools.gh)
        )
        return {
            RuntimeTarget.CODEX.value: core_ready
            and snapshot.tools.codex.status == HostToolStatus.READY,
            RuntimeTarget.CLAUDE_CODE.value: core_ready
            and snapshot.tools.claude.status == HostToolStatus.READY,
        }
