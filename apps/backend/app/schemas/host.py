"""Schemas for host diagnostics endpoints."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


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
    executor_context: HostExecutorContext
    tools: HostDiagnosticsTools
    warnings: list[str] = Field(default_factory=list)


class HostExecutionReadinessResponse(BaseModel):
    """Host-only readiness view for the local execution bridge."""

    generated_at: datetime
    execution_source: HostExecutionSource
    effective_ready: bool
    host_executor_url: str | None = None
    host_executor_reachable: bool = False
    host_executor_error: str | None = None
    host_executor: HostDiagnosticsResponse | None = None
