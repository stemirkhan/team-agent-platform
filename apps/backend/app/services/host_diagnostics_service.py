"""Host diagnostics for local execution prerequisites."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from app.schemas.host import (
    HostDiagnosticsResponse,
    HostDiagnosticsTools,
    HostExecutorContext,
    HostToolDiagnostics,
    HostToolStatus,
)


class HostDiagnosticsService:
    """Collect readiness diagnostics for git, gh, codex, and PTY support."""

    command_timeout_seconds = 10
    minimum_versions = {
        "git": "2.39.0",
        "gh": "2.80.0",
        "codex": "0.100.0",
    }

    def build_snapshot(self) -> HostDiagnosticsResponse:
        """Build a live readiness snapshot from the current process context."""
        git = self._inspect_git()
        gh = self._inspect_gh()
        codex = self._inspect_codex()
        executor_context = self._build_executor_context()
        pty_supported = self._pty_supported()
        warnings = self._build_warnings(
            executor_context=executor_context,
            pty_supported=pty_supported,
            tools=[git, gh, codex],
        )

        ready = pty_supported and all(
            tool.status == HostToolStatus.READY for tool in (git, gh, codex)
        )

        return HostDiagnosticsResponse(
            generated_at=datetime.now(UTC),
            ready=ready,
            pty_supported=pty_supported,
            executor_context=executor_context,
            tools=HostDiagnosticsTools(git=git, gh=gh, codex=codex),
            warnings=warnings,
        )

    def _inspect_git(self) -> HostToolDiagnostics:
        """Return git diagnostics."""
        path = self._resolve_tool_path("git")
        minimum_version = self.minimum_versions["git"]
        if not path:
            return self._missing_tool(
                name="git",
                minimum_version=minimum_version,
                steps=[
                    "Install Git on the host machine.",
                    "Ensure the backend or host executor process can resolve `git` in PATH.",
                ],
            )

        version, version_ok, error_message = self._resolve_version(
            path,
            ["--version"],
            minimum_version,
        )
        if error_message:
            return self._error_tool(
                name="git",
                path=path,
                minimum_version=minimum_version,
                message=error_message,
                steps=[
                    "Run `git --version` in the same environment as the backend process.",
                    "Fix PATH or reinstall Git if the command fails.",
                ],
            )

        if not version_ok:
            return self._outdated_tool(
                name="git",
                path=path,
                version=version,
                minimum_version=minimum_version,
                message=f"Git version {version} is older than required {minimum_version}.",
                steps=[
                    f"Update Git to at least {minimum_version}.",
                    "Restart the backend or host executor after upgrading.",
                ],
            )

        return HostToolDiagnostics(
            name="git",
            found=True,
            path=path,
            version=version,
            minimum_version=minimum_version,
            version_ok=True,
            auth_required=False,
            auth_ok=None,
            status=HostToolStatus.READY,
            message="Git is available in the current execution context.",
        )

    def _inspect_gh(self) -> HostToolDiagnostics:
        """Return GitHub CLI diagnostics."""
        path = self._resolve_tool_path("gh")
        minimum_version = self.minimum_versions["gh"]
        if not path:
            return self._missing_tool(
                name="gh",
                minimum_version=minimum_version,
                steps=[
                    "Install GitHub CLI on the host machine.",
                    "Run `gh auth login` as the same OS user that will execute runs.",
                ],
            )

        version, version_ok, error_message = self._resolve_version(
            path,
            ["--version"],
            minimum_version,
        )
        if error_message:
            return self._error_tool(
                name="gh",
                path=path,
                minimum_version=minimum_version,
                message=error_message,
                steps=[
                    "Run `gh --version` directly in the same environment as the backend process.",
                    "Fix PATH or reinstall GitHub CLI if the command fails.",
                ],
            )

        if not version_ok:
            return self._outdated_tool(
                name="gh",
                path=path,
                version=version,
                minimum_version=minimum_version,
                message=f"GitHub CLI version {version} is older than required {minimum_version}.",
                steps=[
                    f"Update GitHub CLI to at least {minimum_version}.",
                    "Run `gh auth status` again after upgrading.",
                ],
            )

        auth_ok, auth_message = self._check_gh_auth(path)
        if not auth_ok:
            return HostToolDiagnostics(
                name="gh",
                found=True,
                path=path,
                version=version,
                minimum_version=minimum_version,
                version_ok=True,
                auth_required=True,
                auth_ok=False,
                status=HostToolStatus.NOT_AUTHENTICATED,
                message=auth_message,
                remediation_steps=[
                    (
                        "Run `gh auth login` as the same OS user that starts "
                        "the backend or host executor."
                    ),
                    "Verify access with `gh auth status --json hosts`.",
                ],
            )

        return HostToolDiagnostics(
            name="gh",
            found=True,
            path=path,
            version=version,
            minimum_version=minimum_version,
            version_ok=True,
            auth_required=True,
            auth_ok=True,
            status=HostToolStatus.READY,
            message="GitHub CLI is ready and authenticated.",
        )

    def _inspect_codex(self) -> HostToolDiagnostics:
        """Return Codex CLI diagnostics."""
        path = self._resolve_tool_path("codex")
        minimum_version = self.minimum_versions["codex"]
        if not path:
            return self._missing_tool(
                name="codex",
                minimum_version=minimum_version,
                steps=[
                    "Install Codex CLI on the host machine.",
                    (
                        "Run `codex login` using browser or device auth as "
                        "the same OS user that will execute runs."
                    ),
                ],
            )

        version, version_ok, error_message = self._resolve_version(
            path,
            ["--version"],
            minimum_version,
        )
        if error_message:
            return self._error_tool(
                name="codex",
                path=path,
                minimum_version=minimum_version,
                message=error_message,
                steps=[
                    (
                        "Run `codex --version` directly in the same "
                        "environment as the backend process."
                    ),
                    "Fix PATH or reinstall Codex CLI if the command fails.",
                ],
            )

        if not version_ok:
            return self._outdated_tool(
                name="codex",
                path=path,
                version=version,
                minimum_version=minimum_version,
                message=f"Codex CLI version {version} is older than required {minimum_version}.",
                steps=[
                    f"Update Codex CLI to at least {minimum_version}.",
                    "Re-run `codex login status` after upgrading.",
                ],
            )

        auth_ok, auth_message = self._check_codex_auth(path)
        if not auth_ok:
            return HostToolDiagnostics(
                name="codex",
                found=True,
                path=path,
                version=version,
                minimum_version=minimum_version,
                version_ok=True,
                auth_required=True,
                auth_ok=False,
                status=HostToolStatus.NOT_AUTHENTICATED,
                message=auth_message,
                remediation_steps=[
                    (
                        "Run `codex login` using browser or device auth as "
                        "the same OS user that starts the backend or host "
                        "executor."
                    ),
                    "Verify access with `codex login status`.",
                ],
            )

        return HostToolDiagnostics(
            name="codex",
            found=True,
            path=path,
            version=version,
            minimum_version=minimum_version,
            version_ok=True,
            auth_required=True,
            auth_ok=True,
            status=HostToolStatus.READY,
            message="Codex CLI is ready and authenticated.",
        )

    def _build_executor_context(self) -> HostExecutorContext:
        """Return runtime information for the current backend process."""
        container_runtime = self._detect_container_runtime()
        return HostExecutorContext(
            user=os.environ.get("USER") or os.environ.get("USERNAME") or "unknown",
            home=str(Path.home()),
            cwd=os.getcwd(),
            containerized=container_runtime is not None,
            container_runtime=container_runtime,
        )

    @staticmethod
    def _detect_container_runtime() -> str | None:
        """Infer whether the backend process is running in a known container runtime."""
        if Path("/run/.containerenv").exists():
            return "podman"
        if Path("/.dockerenv").exists():
            return "docker"
        return None

    @staticmethod
    def _pty_supported() -> bool:
        """Return whether PTY support is available in the current Python runtime."""
        try:
            import pty  # noqa: F401
        except ImportError:
            return False
        return True

    def _resolve_tool_path(self, name: str) -> str | None:
        """Resolve an executable path from PATH."""
        return shutil.which(name)

    def _run_command(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        """Execute a subprocess and capture text output."""
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=self.command_timeout_seconds,
        )

    def _resolve_version(
        self,
        path: str,
        args: list[str],
        minimum_version: str,
    ) -> tuple[str | None, bool, str | None]:
        """Resolve and compare tool version from a command output."""
        try:
            result = self._run_command([path, *args])
        except (OSError, subprocess.SubprocessError) as exc:
            return None, False, f"Failed to run {Path(path).name}: {exc}"

        if result.returncode != 0:
            detail = self._combine_output(result)
            return None, False, detail or f"{Path(path).name} exited with code {result.returncode}."

        version = self._extract_version(self._combine_output(result))
        if version is None:
            return None, False, f"Could not parse version output from {Path(path).name}."

        return version, self._is_version_at_least(version, minimum_version), None

    def _check_gh_auth(self, path: str) -> tuple[bool, str]:
        """Return GitHub CLI authentication status."""
        try:
            result = self._run_command([path, "auth", "status", "--json", "hosts"])
        except (OSError, subprocess.SubprocessError) as exc:
            return False, f"Failed to run gh auth status: {exc}"

        if result.returncode != 0:
            detail = self._combine_output(result)
            return False, detail or "GitHub CLI authentication is not available."

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return False, "Could not parse `gh auth status --json hosts` output."

        hosts = payload.get("hosts")
        if not isinstance(hosts, dict):
            return False, "GitHub CLI did not return a valid hosts payload."

        for entries in hosts.values():
            if not isinstance(entries, list):
                continue
            for item in entries:
                if not isinstance(item, dict):
                    continue
                if item.get("active") is True and item.get("state") == "success":
                    login = item.get("login")
                    return True, (
                        "Authenticated GitHub host detected for "
                        f"{login or 'current user'}."
                    )

        return False, "No active authenticated GitHub host found."

    def _check_codex_auth(self, path: str) -> tuple[bool, str]:
        """Return Codex CLI authentication status."""
        try:
            result = self._run_command([path, "login", "status"])
        except (OSError, subprocess.SubprocessError) as exc:
            return False, f"Failed to run codex login status: {exc}"

        detail = self._combine_output(result)
        if result.returncode != 0:
            return False, detail or "Codex CLI authentication is not available."

        normalized = detail.lower()
        if "logged in" in normalized:
            return True, detail

        return False, detail or "Codex CLI does not report an active login."

    @staticmethod
    def _combine_output(result: subprocess.CompletedProcess[str]) -> str:
        """Merge stdout and stderr into one readable text block."""
        chunks = [result.stdout.strip(), result.stderr.strip()]
        return "\n".join(chunk for chunk in chunks if chunk)

    @staticmethod
    def _extract_version(output: str) -> str | None:
        """Extract a semantic version from CLI output."""
        match = re.search(r"(\d+\.\d+\.\d+)", output)
        if match is None:
            return None
        return match.group(1)

    @staticmethod
    def _is_version_at_least(version: str, minimum_version: str) -> bool:
        """Compare simple semantic versions using their numeric parts."""
        current = tuple(int(part) for part in version.split("."))
        minimum = tuple(int(part) for part in minimum_version.split("."))
        return current >= minimum

    def _build_warnings(
        self,
        *,
        executor_context: HostExecutorContext,
        pty_supported: bool,
        tools: list[HostToolDiagnostics],
    ) -> list[str]:
        """Collect global warnings that help explain degraded readiness."""
        warnings: list[str] = []

        if executor_context.containerized:
            runtime = executor_context.container_runtime or "container"
            warnings.append(
                f"The backend process is running inside {runtime}. "
                "Host logins for gh or codex may be invisible from this context."
            )

        if not pty_supported:
            warnings.append("PTY support is unavailable, so live terminal streaming cannot start.")

        if any(tool.status == HostToolStatus.MISSING for tool in tools):
            warnings.append(
                "At least one required host tool is missing from PATH in the "
                "current execution context."
            )

        return warnings

    @staticmethod
    def _missing_tool(name: str, minimum_version: str, steps: list[str]) -> HostToolDiagnostics:
        """Build a missing-tool diagnostics payload."""
        return HostToolDiagnostics(
            name=name,
            found=False,
            minimum_version=minimum_version,
            version_ok=False,
            auth_required=name in {"gh", "codex"},
            auth_ok=False if name in {"gh", "codex"} else None,
            status=HostToolStatus.MISSING,
            message=f"{name} was not found in PATH.",
            remediation_steps=steps,
        )

    @staticmethod
    def _error_tool(
        *,
        name: str,
        path: str,
        minimum_version: str,
        message: str,
        steps: list[str],
    ) -> HostToolDiagnostics:
        """Build an error-state diagnostics payload."""
        return HostToolDiagnostics(
            name=name,
            found=True,
            path=path,
            minimum_version=minimum_version,
            version_ok=False,
            auth_required=name in {"gh", "codex"},
            auth_ok=False if name in {"gh", "codex"} else None,
            status=HostToolStatus.ERROR,
            message=message,
            remediation_steps=steps,
        )

    @staticmethod
    def _outdated_tool(
        *,
        name: str,
        path: str,
        version: str | None,
        minimum_version: str,
        message: str,
        steps: list[str],
    ) -> HostToolDiagnostics:
        """Build an outdated-tool diagnostics payload."""
        return HostToolDiagnostics(
            name=name,
            found=True,
            path=path,
            version=version,
            minimum_version=minimum_version,
            version_ok=False,
            auth_required=name in {"gh", "codex"},
            auth_ok=None,
            status=HostToolStatus.OUTDATED,
            message=message,
            remediation_steps=steps,
        )
