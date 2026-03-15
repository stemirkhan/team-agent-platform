"""Tests for host diagnostics endpoints and service behavior."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.api.v1 import host
from app.schemas.host import (
    HostDiagnosticsResponse,
    HostDiagnosticsTools,
    HostExecutorContext,
    HostToolDiagnostics,
    HostToolStatus,
)
from app.services.host_execution_service import HostExecutionReadinessService
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
        durable_transport_ready=True,
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
            claude=HostToolDiagnostics(
                name="claude",
                found=True,
                path="/usr/bin/claude",
                version="2.1.71",
                minimum_version="2.0.0",
                version_ok=True,
                auth_required=True,
                auth_ok=True,
                status=HostToolStatus.READY,
                message="Claude Code CLI is ready.",
            ),
            tmux=HostToolDiagnostics(
                name="tmux",
                found=True,
                path="/usr/bin/tmux",
                version="3.4.0",
                minimum_version="3.2.0",
                version_ok=True,
                auth_required=False,
                auth_ok=None,
                status=HostToolStatus.READY,
                message="tmux is ready.",
            ),
        ),
        warnings=[],
    )

    monkeypatch.setattr(host.readiness_service, "get_host_diagnostics", lambda: snapshot)

    response = client.get("/api/v1/host/diagnostics")

    assert response.status_code == 200
    assert response.json()["ready"] is True
    assert response.json()["tools"]["claude"]["status"] == "ready"
    assert response.json()["tools"]["gh"]["status"] == "ready"
    assert response.json()["tools"]["tmux"]["status"] == "ready"

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
            "claude": None,
            "tmux": None,
        }[name]

    def fake_resolve_version(path: str, args: list[str], minimum_version: str):
        if path.endswith("git"):
            return "2.43.0", True, None
        if path.endswith("tmux"):
            return "3.4.0", True, None
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
    assert snapshot.tools.tmux.status == HostToolStatus.MISSING
    assert snapshot.executor_context.containerized is True
    assert any("podman" in warning.lower() for warning in snapshot.warnings)


def test_host_diagnostics_service_keeps_ready_when_claude_is_missing(monkeypatch) -> None:
    """Claude diagnostics should not downgrade the current Codex-only ready contract."""
    service = HostDiagnosticsService()

    def fake_resolve_tool_path(name: str) -> str | None:
        return {
            "git": "/usr/bin/git",
            "gh": "/usr/bin/gh",
            "codex": "/usr/bin/codex",
            "claude": None,
            "tmux": "/usr/bin/tmux",
        }[name]

    def fake_resolve_version(path: str, args: list[str], minimum_version: str):
        if path.endswith("git"):
            return "2.43.0", True, None
        if path.endswith("gh"):
            return "2.86.0", True, None
        if path.endswith("codex"):
            return "0.112.0", True, None
        return "3.4.0", True, None

    monkeypatch.setattr(service, "_resolve_tool_path", fake_resolve_tool_path)
    monkeypatch.setattr(service, "_resolve_version", fake_resolve_version)
    monkeypatch.setattr(service, "_check_gh_auth", lambda path: (True, "ok"))
    monkeypatch.setattr(service, "_check_codex_auth", lambda path: (True, "ok"))
    monkeypatch.setattr(service, "_detect_container_runtime", lambda: None)
    monkeypatch.setattr(service, "_pty_supported", lambda: True)

    snapshot = service.build_snapshot()

    assert snapshot.ready is True
    assert snapshot.durable_transport_ready is True
    assert snapshot.tools.codex.status == HostToolStatus.READY
    assert snapshot.tools.claude.status == HostToolStatus.MISSING
    assert snapshot.tools.claude.auth_required is True
    assert snapshot.warnings == []


def test_host_diagnostics_service_parses_tmux_two_part_version() -> None:
    """Version parsing should accept tmux outputs like `tmux 3.4`."""
    service = HostDiagnosticsService()

    version, version_ok, error_message = service._resolve_version(
        "/usr/bin/tmux",
        ["-V"],
        "3.2.0",
    )

    assert version == "3.4"
    assert version_ok is True
    assert error_message is None


def test_host_diagnostics_schema_normalizes_legacy_host_executor_payload() -> None:
    """Legacy host-executor snapshots should be accepted and backfilled."""
    snapshot = HostDiagnosticsResponse.model_validate(
        {
            "generated_at": "2026-03-11T17:50:44.431323Z",
            "ready": True,
            "pty_supported": True,
            "executor_context": {
                "user": "temirkhan",
                "home": "/home/temirkhan",
                "cwd": "/home/temirkhan/my-agent-marketplace",
                "containerized": False,
                "container_runtime": None,
            },
            "tools": {
                "git": {
                    "name": "git",
                    "found": True,
                    "path": "/usr/bin/git",
                    "version": "2.43.0",
                    "minimum_version": "2.39.0",
                    "version_ok": True,
                    "auth_required": False,
                    "auth_ok": None,
                    "status": "ready",
                    "message": "Git is available in the current execution context.",
                    "remediation_steps": [],
                },
                "gh": {
                    "name": "gh",
                    "found": True,
                    "path": "/snap/bin/gh",
                    "version": "2.86.0",
                    "minimum_version": "2.80.0",
                    "version_ok": True,
                    "auth_required": True,
                    "auth_ok": True,
                    "status": "ready",
                    "message": "GitHub CLI is ready and authenticated.",
                    "remediation_steps": [],
                },
                "codex": {
                    "name": "codex",
                    "found": True,
                    "path": "/home/temirkhan/.nvm/versions/node/v22.19.0/bin/codex",
                    "version": "0.112.0",
                    "minimum_version": "0.100.0",
                    "version_ok": True,
                    "auth_required": True,
                    "auth_ok": True,
                    "status": "ready",
                    "message": "Codex CLI is ready and authenticated.",
                    "remediation_steps": [],
                },
            },
            "warnings": [],
        }
    )

    assert snapshot.ready is True
    assert snapshot.tools.claude.status == HostToolStatus.MISSING
    assert snapshot.durable_transport_ready is False
    assert snapshot.tools.tmux.status == HostToolStatus.MISSING
    assert "older diagnostics schema" in snapshot.warnings[0].lower()


def test_host_readiness_uses_host_executor_snapshot(
    client: TestClient,
    monkeypatch,
) -> None:
    """Readiness endpoint should expose host-executor diagnostics when configured."""
    host_snapshot = HostDiagnosticsResponse(
        generated_at=datetime.now(UTC),
        ready=True,
        pty_supported=True,
        durable_transport_ready=True,
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
            claude=HostToolDiagnostics(
                name="claude",
                found=True,
                path="/usr/bin/claude",
                version="2.1.71",
                minimum_version="2.0.0",
                version_ok=True,
                auth_required=True,
                auth_ok=True,
                status=HostToolStatus.READY,
                message="claude ready",
            ),
            tmux=HostToolDiagnostics(
                name="tmux",
                found=True,
                path="/usr/bin/tmux",
                version="3.4.0",
                minimum_version="3.2.0",
                version_ok=True,
                auth_required=False,
                auth_ok=None,
                status=HostToolStatus.READY,
                message="tmux ready",
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


def test_host_readiness_can_be_evaluated_for_requested_runtime(
    client: TestClient,
    monkeypatch,
) -> None:
    """Readiness should be runtime-aware instead of remaining globally Codex-centric."""
    host_snapshot = HostDiagnosticsResponse(
        generated_at=datetime.now(UTC),
        ready=False,
        pty_supported=True,
        durable_transport_ready=True,
        executor_context=HostExecutorContext(
            user="temirkhan",
            home="/home/temirkhan",
            cwd="/home/temirkhan/my-agent-marketplace",
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
                found=False,
                path=None,
                version=None,
                minimum_version="0.100.0",
                version_ok=False,
                auth_required=True,
                auth_ok=None,
                status=HostToolStatus.MISSING,
                message="codex missing",
            ),
            claude=HostToolDiagnostics(
                name="claude",
                found=True,
                path="/usr/bin/claude",
                version="2.1.71",
                minimum_version="2.0.0",
                version_ok=True,
                auth_required=True,
                auth_ok=True,
                status=HostToolStatus.READY,
                message="claude ready",
            ),
            tmux=HostToolDiagnostics(
                name="tmux",
                found=True,
                path="/usr/bin/tmux",
                version="3.4",
                minimum_version="3.2.0",
                version_ok=True,
                auth_required=False,
                auth_ok=None,
                status=HostToolStatus.READY,
                message="tmux ready",
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

    response = client.get("/api/v1/host/readiness?runtime_target=claude_code")

    assert response.status_code == 200
    payload = response.json()
    assert payload["requested_runtime"] == "claude_code"
    assert payload["effective_ready"] is True
    assert payload["runtime_ready"]["codex"] is False
    assert payload["runtime_ready"]["claude_code"] is True


def test_host_execution_readiness_service_retries_transient_timeout(monkeypatch) -> None:
    """Transient host-executor timeouts should be retried before degrading readiness."""
    service = HostExecutionReadinessService(
        Settings(host_executor_base_url="http://host.containers.internal:8765")
    )
    snapshot = HostDiagnosticsResponse(
        generated_at=datetime.now(UTC),
        ready=True,
        pty_supported=True,
        durable_transport_ready=True,
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
                version="0.112.0",
                minimum_version="0.100.0",
                version_ok=True,
                auth_required=True,
                auth_ok=True,
                status=HostToolStatus.READY,
                message="codex ready",
            ),
            claude=HostToolDiagnostics(
                name="claude",
                found=True,
                path="/usr/bin/claude",
                version="2.1.71",
                minimum_version="2.0.0",
                version_ok=True,
                auth_required=True,
                auth_ok=True,
                status=HostToolStatus.READY,
                message="claude ready",
            ),
            tmux=HostToolDiagnostics(
                name="tmux",
                found=True,
                path="/usr/bin/tmux",
                version="3.4",
                minimum_version="3.2.0",
                version_ok=True,
                auth_required=False,
                auth_ok=None,
                status=HostToolStatus.READY,
                message="tmux ready",
            ),
        ),
        warnings=[],
    )
    attempts = {"count": 0}

    def fake_fetch_once(base_url: str):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return None, "Host executor request failed: timed out."
        return snapshot, None

    monkeypatch.setattr(service, "_fetch_host_executor_snapshot_once", fake_fetch_once)
    monkeypatch.setattr("app.services.host_execution_service.time.sleep", lambda _: None)

    readiness = service.build_readiness()

    assert attempts["count"] == 2
    assert readiness.effective_ready is True
    assert readiness.host_executor_reachable is True
    assert readiness.host_executor is not None
