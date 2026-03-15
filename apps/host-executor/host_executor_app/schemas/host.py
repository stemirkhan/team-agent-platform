"""Schemas for host executor diagnostics."""

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
    claude: HostToolDiagnostics
    tmux: HostToolDiagnostics


class HostExecutorContext(BaseModel):
    """Execution context for the host executor process."""

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
