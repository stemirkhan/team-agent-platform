"""Schemas for host diagnostics endpoints."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class HostToolStatus(StrEnum):
    """Normalized readiness state for a host tool."""

    READY = "ready"
    MISSING = "missing"
    OUTDATED = "outdated"
    NOT_AUTHENTICATED = "not_authenticated"
    ERROR = "error"


class HostExecutionSource(StrEnum):
    """Effective execution source for Codex and GitHub CLI interactions."""

    HOST_EXECUTOR = "host_executor"


def _legacy_tmux_diagnostics() -> dict[str, Any]:
    """Return a synthetic tmux diagnostics block for older host-executor payloads."""
    return {
        "name": "tmux",
        "found": False,
        "path": None,
        "version": None,
        "minimum_version": "3.2.0",
        "version_ok": False,
        "auth_required": False,
        "auth_ok": None,
        "status": HostToolStatus.MISSING,
        "message": "This host executor build does not report tmux diagnostics yet.",
        "remediation_steps": [
            "Restart or redeploy the host executor to pick up the latest diagnostics schema."
        ],
    }


class HostToolDiagnostics(BaseModel):
    """Diagnostics snapshot for a single host tool."""

    name: str
    found: bool
    path: str | None = None
    version: str | None = None
    minimum_version: str
    version_ok: bool = False
    auth_required: bool = False
    auth_ok: bool | None = None
    status: HostToolStatus
    message: str
    remediation_steps: list[str] = Field(default_factory=list)


class HostDiagnosticsTools(BaseModel):
    """Grouped diagnostics for required host tools."""

    git: HostToolDiagnostics
    gh: HostToolDiagnostics
    codex: HostToolDiagnostics
    tmux: HostToolDiagnostics

    @model_validator(mode="before")
    @classmethod
    def add_legacy_tmux_snapshot(cls, value: Any) -> Any:
        """Inject tmux diagnostics when the host executor still returns the legacy shape."""
        if not isinstance(value, dict) or "tmux" in value:
            return value

        normalized = dict(value)
        normalized["tmux"] = _legacy_tmux_diagnostics()
        return normalized


class HostExecutorContext(BaseModel):
    """Execution context of the backend process collecting diagnostics."""

    user: str
    home: str
    cwd: str
    containerized: bool
    container_runtime: str | None = None


class HostDiagnosticsResponse(BaseModel):
    """Response payload for host diagnostics snapshots."""

    generated_at: datetime
    ready: bool
    pty_supported: bool
    durable_transport_ready: bool
    executor_context: HostExecutorContext
    tools: HostDiagnosticsTools
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_payload(cls, value: Any) -> Any:
        """Backfill fields that were added after the original host diagnostics payload."""
        if not isinstance(value, dict):
            return value

        normalized = dict(value)

        if "durable_transport_ready" not in normalized:
            tools = normalized.get("tools")
            durable_transport_ready = False
            if isinstance(tools, dict):
                tmux = tools.get("tmux")
                if isinstance(tmux, dict):
                    durable_transport_ready = tmux.get("status") in (
                        HostToolStatus.READY,
                        HostToolStatus.READY.value,
                    )

            normalized["durable_transport_ready"] = durable_transport_ready
            warning = (
                "Host executor is running an older diagnostics schema, so durable "
                "transport metadata is inferred."
            )
            warnings = list(normalized.get("warnings") or [])
            if warning not in warnings:
                warnings.append(warning)
            normalized["warnings"] = warnings

        return normalized


class HostExecutionReadinessResponse(BaseModel):
    """Host-only readiness view for the local execution bridge."""

    generated_at: datetime
    execution_source: HostExecutionSource
    effective_ready: bool
    host_executor_url: str | None = None
    host_executor_reachable: bool = False
    host_executor_error: str | None = None
    host_executor: HostDiagnosticsResponse | None = None
