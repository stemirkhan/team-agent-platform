"""Shared wiring for run-related backend services."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.repositories.agent import AgentRepository
from app.repositories.agent_version import AgentVersionRepository
from app.repositories.export_job import ExportJobRepository
from app.repositories.run import RunRepository
from app.repositories.team import TeamRepository
from app.services.claude_proxy_service import ClaudeProxyService
from app.services.codex_proxy_service import CodexProxyService
from app.services.export_service import ExportService
from app.services.github_proxy_service import GitHubProxyService
from app.services.host_execution_service import HostExecutionReadinessService
from app.services.run_report_service import RunReportService
from app.services.run_service import RunService
from app.services.run_session_sync_service import RunSessionSyncService
from app.services.run_state_service import RunStateService
from app.services.run_workspace_materializer import RunWorkspaceMaterializer
from app.services.runtime_adapters import (
    ClaudeRuntimeAdapter,
    CodexRuntimeAdapter,
    RuntimeAdapterRegistry,
)
from app.services.workspace_proxy_service import WorkspaceProxyService


def build_run_service(db: Session, settings: Settings | None = None) -> RunService:
    """Build RunService with shared runtime/session subservices."""
    resolved_settings = settings or get_settings()
    run_repository = RunRepository(db)
    team_repository = TeamRepository(db)
    export_repository = ExportJobRepository(db)
    agent_repository = AgentRepository(db)
    agent_version_repository = AgentVersionRepository(db)
    export_service = ExportService(
        export_repository,
        agent_repository,
        agent_version_repository,
        team_repository,
    )
    workspace_proxy_service = WorkspaceProxyService(resolved_settings)
    codex_proxy_service = CodexProxyService(resolved_settings)
    claude_proxy_service = ClaudeProxyService(resolved_settings)
    github_proxy_service = GitHubProxyService(resolved_settings)
    readiness_service = HostExecutionReadinessService(resolved_settings)
    runtime_adapters = RuntimeAdapterRegistry(
        adapters=[
            CodexRuntimeAdapter(codex_proxy_service),
            ClaudeRuntimeAdapter(claude_proxy_service),
        ]
    )
    state_service = RunStateService(run_repository)
    session_sync_service = RunSessionSyncService(
        run_repository=run_repository,
        workspace_proxy_service=workspace_proxy_service,
        runtime_adapters=runtime_adapters,
        state_service=state_service,
    )
    report_service = RunReportService(
        run_repository=run_repository,
        workspace_proxy_service=workspace_proxy_service,
        runtime_adapters=runtime_adapters,
    )
    workspace_materializer = RunWorkspaceMaterializer(
        export_service=export_service,
        runtime_adapters=runtime_adapters,
    )
    return RunService(
        run_repository,
        team_repository,
        export_service,
        workspace_proxy_service,
        codex_proxy_service,
        claude_proxy_service,
        github_proxy_service,
        readiness_service,
        runtime_adapters=runtime_adapters,
        state_service=state_service,
        session_sync_service=session_sync_service,
        report_service=report_service,
        workspace_materializer=workspace_materializer,
    )
