"""Tests for host diagnostics endpoints and service behavior."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.api.v1 import host
from app.schemas.host import (
    HostDiagnosticsResponse,
    HostDiagnosticsTools,
    HostExecutorContext,
    HostToolDiagnostics,
    HostToolStatus,
)
from app.services.host_diagnostics_service import HostDiagnosticsService


def test_host_diagnostics_endpoint_returns_snapshot(
    client: TestClient,
    monkeypatch,
) -> None:
    """Diagnostics endpoint should return normalized tool readiness payload."""
    snapshot = HostDiagnosticsResponse(
        generated_at=datetime.now(UTC),
        ready=True,
        pty_supported=True,
        executor_context=HostExecutorContext(
            user="tester",
            home="/tmp/tester",
            cwd="/workspace",
            containerized=False,
            container_runtime=None,
        ),
        tools=HostDiagnosticsTools(
            git=HostToolDiagnostics(
                name="git",
                found=True,
                path="/usr/bin/git",
                version="2.43.0",
                minimum_version="2.39.0",
                version_ok=True,
                auth_required=False,
                auth_ok=None,
                status=HostToolStatus.READY,
                message="Git is available.",
            ),
            gh=HostToolDiagnostics(
                name="gh",
                found=True,
                path="/usr/bin/gh",
                version="2.86.0",
                minimum_version="2.80.0",
                version_ok=True,
                auth_required=True,
                auth_ok=True,
                status=HostToolStatus.READY,
                message="GitHub CLI is ready.",
            ),
            codex=HostToolDiagnostics(
                name="codex",
                found=True,
                path="/usr/bin/codex",
                version="0.108.0",
                minimum_version="0.100.0",
                version_ok=True,
                auth_required=True,
                auth_ok=True,
                status=HostToolStatus.READY,
                message="Codex CLI is ready.",
            ),
        ),
        warnings=[],
    )

    monkeypatch.setattr(host.readiness_service, "get_host_diagnostics", lambda: snapshot)

    response = client.get("/api/v1/host/diagnostics")

    assert response.status_code == 200
    assert response.json()["ready"] is True
    assert response.json()["tools"]["gh"]["status"] == "ready"

    refresh_response = client.post("/api/v1/host/diagnostics/refresh")
    assert refresh_response.status_code == 200
    assert refresh_response.json()["tools"]["codex"]["version"] == "0.108.0"


def test_host_diagnostics_endpoint_returns_503_when_host_executor_is_unavailable(
    client: TestClient,
    monkeypatch,
) -> None:
    """Diagnostics endpoint should fail explicitly when host executor is unavailable."""
    monkeypatch.setattr(
        host.readiness_service,
        "get_host_diagnostics",
        lambda: (_ for _ in ()).throw(
            host.HostExecutionReadinessServiceError("Host executor is unreachable.")
        ),
    )

    response = client.get("/api/v1/host/diagnostics")

    assert response.status_code == 503
    assert response.json()["detail"] == "Host executor is unreachable."


def test_host_diagnostics_service_marks_missing_codex(monkeypatch) -> None:
    """Diagnostics service should degrade readiness when codex is missing."""
    service = HostDiagnosticsService()

    def fake_resolve_tool_path(name: str) -> str | None:
        return {
            "git": "/usr/bin/git",
            "gh": "/usr/bin/gh",
            "codex": None,
        }[name]

    def fake_resolve_version(path: str, args: list[str], minimum_version: str):
        if path.endswith("git"):
            return "2.43.0", True, None
        return "2.86.0", True, None

    monkeypatch.setattr(service, "_resolve_tool_path", fake_resolve_tool_path)
    monkeypatch.setattr(service, "_resolve_version", fake_resolve_version)
    monkeypatch.setattr(service, "_check_gh_auth", lambda path: (True, "ok"))
    monkeypatch.setattr(service, "_check_codex_auth", lambda path: (True, "ok"))
    monkeypatch.setattr(service, "_detect_container_runtime", lambda: "podman")
    monkeypatch.setattr(service, "_pty_supported", lambda: True)

    snapshot = service.build_snapshot()

    assert snapshot.ready is False
    assert snapshot.tools.git.status == HostToolStatus.READY
    assert snapshot.tools.gh.status == HostToolStatus.READY
    assert snapshot.tools.codex.status == HostToolStatus.MISSING
    assert snapshot.executor_context.containerized is True
    assert any("podman" in warning.lower() for warning in snapshot.warnings)


def test_host_readiness_uses_host_executor_snapshot(
    client: TestClient,
    monkeypatch,
) -> None:
    """Readiness endpoint should expose host-executor diagnostics when configured."""
    host_snapshot = HostDiagnosticsResponse(
        generated_at=datetime.now(UTC),
        ready=True,
        pty_supported=True,
        executor_context=HostExecutorContext(
            user="temirkhan",
            home="/home/temirkhan",
            cwd="/home/temirkhan",
            containerized=False,
            container_runtime=None,
        ),
        tools=HostDiagnosticsTools(
            git=HostToolDiagnostics(
                name="git",
                found=True,
                path="/usr/bin/git",
                version="2.43.0",
                minimum_version="2.39.0",
                version_ok=True,
                auth_required=False,
                auth_ok=None,
                status=HostToolStatus.READY,
                message="git ready",
            ),
            gh=HostToolDiagnostics(
                name="gh",
                found=True,
                path="/usr/bin/gh",
                version="2.86.0",
                minimum_version="2.80.0",
                version_ok=True,
                auth_required=True,
                auth_ok=True,
                status=HostToolStatus.READY,
                message="gh ready",
            ),
            codex=HostToolDiagnostics(
                name="codex",
                found=True,
                path="/usr/bin/codex",
                version="0.108.0",
                minimum_version="0.100.0",
                version_ok=True,
                auth_required=True,
                auth_ok=True,
                status=HostToolStatus.READY,
                message="codex ready",
            ),
        ),
        warnings=[],
    )

    monkeypatch.setattr(
        host.readiness_service,
        "_normalize_base_url",
        lambda value: "http://host.containers.internal:8765",
    )
    monkeypatch.setattr(
        host.readiness_service,
        "_fetch_host_executor_snapshot",
        lambda base_url: (host_snapshot, None),
    )

    response = client.get("/api/v1/host/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_source"] == "host_executor"
    assert payload["effective_ready"] is True
    assert payload["host_executor_reachable"] is True
    assert payload["host_executor"]["tools"]["codex"]["status"] == "ready"
    assert "backend" not in payload


def test_host_readiness_reports_unreachable_host_executor(
    client: TestClient,
    monkeypatch,
) -> None:
    """Readiness endpoint should report bridge reachability failures explicitly."""
    monkeypatch.setattr(
        host.readiness_service,
        "_normalize_base_url",
        lambda value: "http://host.containers.internal:8765",
    )
    monkeypatch.setattr(
        host.readiness_service,
        "_fetch_host_executor_snapshot",
        lambda base_url: (None, "Host executor is unreachable."),
    )

    response = client.post("/api/v1/host/readiness/refresh")

    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_source"] == "host_executor"
    assert payload["effective_ready"] is False
    assert payload["host_executor_reachable"] is False
    assert payload["host_executor_error"] == "Host executor is unreachable."


def test_host_readiness_reports_missing_host_executor_configuration(
    client: TestClient,
    monkeypatch,
) -> None:
    """Readiness endpoint should report missing host executor configuration explicitly."""
    monkeypatch.setattr(
        host.readiness_service,
        "_normalize_base_url",
        lambda value: None,
    )

    response = client.get("/api/v1/host/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_source"] == "host_executor"
    assert payload["effective_ready"] is False
    assert payload["host_executor_reachable"] is False
    assert "HOST_EXECUTOR_BASE_URL" in payload["host_executor_error"]
