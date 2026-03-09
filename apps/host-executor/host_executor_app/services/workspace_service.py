"""Workspace lifecycle service backed by host git and gh subprocesses."""

from __future__ import annotations

import json
import shutil
import subprocess
import tomllib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from host_executor_app.core.config import get_settings
from host_executor_app.schemas.workspace import (
    WorkspaceCommandResult,
    WorkspaceCommandsRun,
    WorkspaceCommandsRunResponse,
    WorkspaceCommit,
    WorkspaceExecutionConfigRead,
    WorkspaceListResponse,
    WorkspaceMaterialize,
    WorkspacePrepare,
    WorkspacePullRequestCreate,
    WorkspaceRead,
)
from host_executor_app.services.github_tracker_service import (
    GitHubTrackerService,
    GitHubTrackerServiceError,
)


@dataclass(slots=True)
class WorkspaceServiceError(Exception):
    """Normalized error raised for workspace lifecycle failures."""

    status_code: int
    detail: str


class WorkspaceService:
    """Manage local workspaces for clone, branch, commit, push, and draft PR flow."""

    _MATERIALIZED_STATE_FILENAME = ".materialized-files.json"
    _EXECUTION_CONFIG_FILENAMES = (".team-agent-platform.toml", "team-agent-platform.toml")

    def __init__(self) -> None:
        self.settings = get_settings()
        self.github_tracker = GitHubTrackerService()
        self.workspace_root = Path(self.settings.workspace_root).expanduser().resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)

    def list_workspaces(self) -> WorkspaceListResponse:
        """Return all persisted workspaces ordered by newest update first."""
        items: list[WorkspaceRead] = []
        for metadata_path in self.workspace_root.glob("*/metadata.json"):
            try:
                items.append(self._load_workspace_from_path(metadata_path))
            except WorkspaceServiceError:
                continue

        items.sort(key=lambda item: item.updated_at, reverse=True)
        return WorkspaceListResponse(items=items, total=len(items))

    def prepare_workspace(self, payload: WorkspacePrepare) -> WorkspaceRead:
        """Clone a repository, checkout base, and create a working branch."""
        try:
            repo = self.github_tracker.get_repo(payload.owner, payload.repo)
        except GitHubTrackerServiceError as exc:
            raise WorkspaceServiceError(exc.status_code, exc.detail) from exc

        workspace_id = uuid.uuid4().hex
        workspace_dir = self.workspace_root / workspace_id
        repo_dir = workspace_dir / "repo"
        workspace_dir.mkdir(parents=True, exist_ok=False)

        remote_url = self._build_remote_url(repo.url)
        base_branch = payload.base_branch or repo.default_branch or "main"
        working_branch = payload.working_branch or self._generate_working_branch(repo.name)
        timestamp = _utc_now()

        metadata = WorkspaceRead(
            id=workspace_id,
            repo_owner=repo.owner,
            repo_name=repo.name,
            repo_full_name=repo.full_name,
            remote_url=remote_url,
            workspace_path=str(workspace_dir),
            repo_path=str(repo_dir),
            base_branch=base_branch,
            working_branch=working_branch,
            status="prepared",
            created_at=timestamp,
            updated_at=timestamp,
        )

        try:
            self._run_gh(
                [
                    "repo",
                    "clone",
                    repo.full_name,
                    str(repo_dir),
                    "--",
                    "--depth=1",
                    f"--branch={base_branch}",
                    "--single-branch",
                ],
                label="clone repository",
                cwd=workspace_dir,
            )
            self._run_git(
                ["checkout", "-b", working_branch],
                cwd=repo_dir,
                label="create working branch",
            )
            refreshed = self._refresh_workspace(metadata)
        except Exception:
            shutil.rmtree(workspace_dir, ignore_errors=True)
            raise

        self._save_workspace(refreshed)
        return refreshed

    def get_workspace(self, workspace_id: str) -> WorkspaceRead:
        """Return one workspace with freshly computed git status."""
        metadata = self._load_workspace(workspace_id)
        refreshed = self._refresh_workspace(metadata)
        self._save_workspace(refreshed)
        return refreshed

    def get_execution_config(self, workspace_id: str) -> WorkspaceExecutionConfigRead:
        """Return normalized repo-level execution config for one workspace."""
        metadata = self._load_workspace(workspace_id)
        repo_dir = Path(metadata.repo_path)
        if not repo_dir.exists():
            raise WorkspaceServiceError(404, f"Workspace repo path is missing: {repo_dir}")
        return self._load_execution_config(repo_dir)

    def run_commands(
        self,
        workspace_id: str,
        payload: WorkspaceCommandsRun,
    ) -> WorkspaceCommandsRunResponse:
        """Run sequential shell commands inside one workspace and return normalized results."""
        metadata = self._load_workspace(workspace_id)
        repo_dir = Path(metadata.repo_path)
        if not repo_dir.exists():
            raise WorkspaceServiceError(404, f"Workspace repo path is missing: {repo_dir}")

        command_cwd = self._resolve_repo_directory_path(
            repo_dir=repo_dir,
            relative_path=payload.working_directory,
        )
        items: list[WorkspaceCommandResult] = []
        failed_command: str | None = None

        for command in payload.commands:
            started_at = _utc_now()
            try:
                completed = subprocess.run(
                    ["zsh", "-lc", command],
                    capture_output=True,
                    check=False,
                    text=True,
                    cwd=str(command_cwd),
                    timeout=self.settings.workspace_command_timeout_seconds,
                )
            except FileNotFoundError as exc:
                raise WorkspaceServiceError(
                    503,
                    "The host shell required for workspace commands was not found.",
                ) from exc
            except subprocess.TimeoutExpired as exc:
                raise WorkspaceServiceError(
                    504,
                    (
                        "Workspace command timed out after "
                        f"{self.settings.workspace_command_timeout_seconds} seconds: {command}"
                    ),
                ) from exc
            except OSError as exc:
                raise WorkspaceServiceError(
                    503,
                    f"Failed to launch workspace command `{command}`: {exc}",
                ) from exc

            output = "\n".join(
                part
                for part in [completed.stdout.strip(), completed.stderr.strip()]
                if part
            )
            result = WorkspaceCommandResult(
                command=command,
                exit_code=completed.returncode,
                output=output,
                started_at=started_at,
                finished_at=_utc_now(),
                succeeded=completed.returncode == 0,
            )
            items.append(result)
            if completed.returncode != 0:
                failed_command = command
                break

        refreshed = self._refresh_workspace(metadata)
        self._save_workspace(refreshed)
        return WorkspaceCommandsRunResponse(
            label=payload.label,
            working_directory=str(PurePosixPath(payload.working_directory.strip() or ".")),
            success=failed_command is None,
            failed_command=failed_command,
            items=items,
        )

    def commit_workspace(self, workspace_id: str, payload: WorkspaceCommit) -> WorkspaceRead:
        """Commit local changes in a prepared workspace."""
        metadata = self.get_workspace(workspace_id)
        if not metadata.has_changes:
            raise WorkspaceServiceError(409, "Workspace has no changes to commit.")

        repo_dir = Path(metadata.repo_path)
        self._run_git(["add", "-A"], cwd=repo_dir, label="stage changes")
        self._run_git(
            ["commit", "-m", payload.message.strip()],
            cwd=repo_dir,
            label="commit changes",
        )

        refreshed = self._refresh_workspace(metadata)
        updated = refreshed.model_copy(
            update={
                "status": "committed",
                "last_commit_message": payload.message.strip(),
                "committed_at": _utc_now(),
                "updated_at": _utc_now(),
            }
        )
        self._save_workspace(updated)
        return updated

    def materialize_workspace(
        self,
        workspace_id: str,
        payload: WorkspaceMaterialize,
    ) -> WorkspaceRead:
        """Write text files into a prepared workspace repo."""
        metadata = self._load_workspace(workspace_id)
        repo_dir = Path(metadata.repo_path)
        if not repo_dir.exists():
            raise WorkspaceServiceError(404, f"Workspace repo path is missing: {repo_dir}")

        materialized_state = self._load_materialized_state(metadata)
        for file in payload.files:
            target_path = self._resolve_repo_file_path(repo_dir=repo_dir, relative_path=file.path)
            state_key = str(PurePosixPath(file.path.strip()))
            if state_key not in materialized_state:
                materialized_state[state_key] = self._capture_file_state(target_path)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(file.content, encoding="utf-8")

        self._save_materialized_state(metadata, materialized_state)
        refreshed = self._refresh_workspace(metadata)
        self._save_workspace(refreshed)
        return refreshed

    def cleanup_materialized_files(self, workspace_id: str) -> WorkspaceRead:
        """Restore or delete files previously materialized into the repo workspace."""
        metadata = self._load_workspace(workspace_id)
        repo_dir = Path(metadata.repo_path)
        if not repo_dir.exists():
            raise WorkspaceServiceError(404, f"Workspace repo path is missing: {repo_dir}")

        materialized_state = self._load_materialized_state(metadata)
        if not materialized_state:
            refreshed = self._refresh_workspace(metadata)
            self._save_workspace(refreshed)
            return refreshed

        for relative_path, entry in materialized_state.items():
            target_path = self._resolve_repo_file_path(
                repo_dir=repo_dir,
                relative_path=relative_path,
            )
            existed_before = bool(entry.get("existed"))
            previous_content = entry.get("content")

            if existed_before:
                if not isinstance(previous_content, str):
                    raise WorkspaceServiceError(
                        500,
                        f"Materialized file state is invalid for `{relative_path}`.",
                    )
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(previous_content, encoding="utf-8")
                continue

            if target_path.exists():
                target_path.unlink(missing_ok=True)
                self._prune_empty_directories(target_path.parent, stop_at=repo_dir.resolve())

        self._delete_materialized_state(metadata)
        refreshed = self._refresh_workspace(metadata)
        self._save_workspace(refreshed)
        return refreshed

    def push_workspace(self, workspace_id: str) -> WorkspaceRead:
        """Push the current working branch to origin."""
        metadata = self.get_workspace(workspace_id)
        repo_dir = Path(metadata.repo_path)
        self._run_git(
            ["push", "--set-upstream", "origin", metadata.working_branch],
            cwd=repo_dir,
            label="push working branch",
        )

        refreshed = self._refresh_workspace(metadata)
        updated = refreshed.model_copy(
            update={
                "status": "pushed",
                "pushed_at": _utc_now(),
                "updated_at": _utc_now(),
            }
        )
        self._save_workspace(updated)
        return updated

    def create_pull_request(
        self,
        workspace_id: str,
        payload: WorkspacePullRequestCreate,
    ) -> WorkspaceRead:
        """Create a draft or ready PR from the current branch and persist its URL."""
        metadata = self.get_workspace(workspace_id)
        args = [
            "pr",
            "create",
            "--repo",
            metadata.repo_full_name,
            "--base",
            metadata.base_branch,
            "--head",
            metadata.working_branch,
            "--title",
            payload.title.strip(),
            "--body",
            payload.body or "",
        ]
        if payload.draft:
            args.append("--draft")

        self._run_gh(args, label="create pull request")
        pull = self._view_pull_by_reference(metadata.repo_full_name, metadata.working_branch)

        updated = metadata.model_copy(
            update={
                "status": "pull_request_created",
                "pull_request_number": pull["number"],
                "pull_request_url": pull["url"],
                "updated_at": _utc_now(),
            }
        )
        self._save_workspace(updated)
        return updated

    def delete_workspace(self, workspace_id: str) -> None:
        """Delete a persisted workspace directory."""
        metadata = self._load_workspace(workspace_id)
        workspace_dir = Path(metadata.workspace_path)
        if workspace_dir.exists():
            shutil.rmtree(workspace_dir, ignore_errors=True)

    def _refresh_workspace(self, metadata: WorkspaceRead) -> WorkspaceRead:
        """Recompute git state for an existing workspace."""
        repo_dir = Path(metadata.repo_path)
        if not repo_dir.exists():
            raise WorkspaceServiceError(404, f"Workspace repo path is missing: {repo_dir}")

        current_branch = self._run_git(
            ["rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_dir,
            label="read current branch",
        ).stdout.strip()

        last_commit_sha = self._run_git(
            ["rev-parse", "HEAD"],
            cwd=repo_dir,
            label="read last commit sha",
        ).stdout.strip()

        upstream_branch = self._try_run_git(
            ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            cwd=repo_dir,
        )

        status_output = self._run_git(
            ["status", "--porcelain=v1"],
            cwd=repo_dir,
            label="read git status",
        ).stdout
        changed_files = self._parse_git_status(status_output)

        return metadata.model_copy(
            update={
                "current_branch": current_branch or None,
                "upstream_branch": upstream_branch.strip() or None if upstream_branch else None,
                "has_changes": len(changed_files) > 0,
                "changed_files": changed_files,
                "last_commit_sha": last_commit_sha or None,
                "updated_at": _utc_now(),
            }
        )

    def _load_workspace(self, workspace_id: str) -> WorkspaceRead:
        """Load workspace metadata by ID."""
        metadata_path = self.workspace_root / workspace_id / "metadata.json"
        return self._load_workspace_from_path(metadata_path)

    def _load_workspace_from_path(self, metadata_path: Path) -> WorkspaceRead:
        """Load workspace metadata from one persisted metadata file."""
        if not metadata_path.exists():
            raise WorkspaceServiceError(404, "Workspace metadata was not found.")

        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise WorkspaceServiceError(
                500,
                f"Workspace metadata is corrupted: {metadata_path}",
            ) from exc

        try:
            return WorkspaceRead.model_validate(payload)
        except Exception as exc:  # noqa: BLE001
            raise WorkspaceServiceError(
                500,
                f"Workspace metadata is invalid: {metadata_path}",
            ) from exc

    def _save_workspace(self, metadata: WorkspaceRead) -> None:
        """Persist workspace metadata next to the cloned repo."""
        metadata_path = Path(metadata.workspace_path) / "metadata.json"
        metadata_path.write_text(
            json.dumps(metadata.model_dump(), ensure_ascii=True, indent=2),
            encoding="utf-8",
        )

    def _load_materialized_state(
        self,
        metadata: WorkspaceRead,
    ) -> dict[str, dict[str, object | None]]:
        """Return persisted original file state for materialized run scaffolding."""
        state_path = Path(metadata.workspace_path) / self._MATERIALIZED_STATE_FILENAME
        if not state_path.exists():
            return {}
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise WorkspaceServiceError(
                500,
                f"Workspace materialized state is corrupted: {state_path}",
            ) from exc
        if not isinstance(payload, dict):
            raise WorkspaceServiceError(
                500,
                f"Workspace materialized state is invalid: {state_path}",
            )
        normalized: dict[str, dict[str, object | None]] = {}
        for path, value in payload.items():
            if isinstance(path, str) and isinstance(value, dict):
                normalized[path] = value
        return normalized

    def _save_materialized_state(
        self,
        metadata: WorkspaceRead,
        state: dict[str, dict[str, object | None]],
    ) -> None:
        """Persist original file state for later cleanup after Codex finishes."""
        state_path = Path(metadata.workspace_path) / self._MATERIALIZED_STATE_FILENAME
        state_path.write_text(
            json.dumps(state, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )

    def _delete_materialized_state(self, metadata: WorkspaceRead) -> None:
        """Delete persisted materialized state after cleanup finishes."""
        state_path = Path(metadata.workspace_path) / self._MATERIALIZED_STATE_FILENAME
        if state_path.exists():
            state_path.unlink()

    @staticmethod
    def _capture_file_state(target_path: Path) -> dict[str, object | None]:
        """Capture original file content before overwriting it with run scaffolding."""
        if not target_path.exists():
            return {"existed": False, "content": None}
        try:
            return {
                "existed": True,
                "content": target_path.read_text(encoding="utf-8"),
            }
        except UnicodeDecodeError as exc:
            raise WorkspaceServiceError(
                409,
                (
                    f"Refusing to overwrite non-UTF-8 file `{target_path.name}` "
                    "with run scaffolding. "
                    "Remove or rename the conflicting file and retry the run."
                ),
            ) from exc

    @staticmethod
    def _prune_empty_directories(start: Path, *, stop_at: Path) -> None:
        """Remove empty directories created for run scaffolding without touching the repo root."""
        current = start.resolve()
        while current != stop_at:
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent

    def _load_execution_config(self, repo_dir: Path) -> WorkspaceExecutionConfigRead:
        """Read repo-level execution config when present and normalize it."""
        config_path = self._find_execution_config_path(repo_dir)
        if config_path is None:
            return WorkspaceExecutionConfigRead()

        try:
            payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            raise WorkspaceServiceError(
                422,
                f"Repo execution config is invalid: {config_path.name}",
            ) from exc
        if not isinstance(payload, dict):
            raise WorkspaceServiceError(
                422,
                f"Repo execution config must be a TOML table: {config_path.name}",
            )

        run_section = payload.get("run") if isinstance(payload.get("run"), dict) else {}
        setup_section = payload.get("setup") if isinstance(payload.get("setup"), dict) else {}
        checks_section = payload.get("checks") if isinstance(payload.get("checks"), dict) else {}

        run_working_directory = self._normalize_working_directory(
            repo_dir=repo_dir,
            value=run_section.get("working_directory"),
            field_name="run.working_directory",
        )
        setup_working_directory = self._normalize_working_directory(
            repo_dir=repo_dir,
            value=setup_section.get("working_directory", run_working_directory),
            field_name="setup.working_directory",
        )
        check_working_directory = self._normalize_working_directory(
            repo_dir=repo_dir,
            value=checks_section.get("working_directory", run_working_directory),
            field_name="checks.working_directory",
        )

        return WorkspaceExecutionConfigRead(
            source_path=config_path.name,
            run_working_directory=run_working_directory,
            setup_working_directory=setup_working_directory,
            setup_commands=self._normalize_command_list(
                setup_section.get("commands"),
                field_name="setup.commands",
            ),
            check_working_directory=check_working_directory,
            check_commands=self._normalize_command_list(
                checks_section.get("commands"),
                field_name="checks.commands",
            ),
        )

    def _find_execution_config_path(self, repo_dir: Path) -> Path | None:
        """Return the first supported repo execution config file under the repo root."""
        for filename in self._EXECUTION_CONFIG_FILENAMES:
            candidate = repo_dir / filename
            if candidate.exists():
                return candidate
        return None

    def _normalize_working_directory(
        self,
        *,
        repo_dir: Path,
        value: object,
        field_name: str,
    ) -> str:
        """Validate and normalize a repo-relative working directory string."""
        normalized = "." if value is None else str(value).strip()
        if not normalized:
            raise WorkspaceServiceError(
                422,
                f"Repo execution config field `{field_name}` must not be empty.",
            )
        self._resolve_repo_directory_path(repo_dir=repo_dir, relative_path=normalized)
        return str(PurePosixPath(normalized))

    @staticmethod
    def _normalize_command_list(value: object, *, field_name: str) -> list[str]:
        """Validate a list of shell commands from repo execution config."""
        if value is None:
            return []
        if not isinstance(value, list):
            raise WorkspaceServiceError(
                422,
                f"Repo execution config field `{field_name}` must be a list.",
            )

        commands: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise WorkspaceServiceError(
                    422,
                    f"Repo execution config field `{field_name}` must contain non-empty strings.",
                )
            commands.append(item.strip())
        return commands

    def _run_git(
        self,
        args: list[str],
        *,
        cwd: Path,
        label: str,
    ) -> subprocess.CompletedProcess[str]:
        """Run a git subprocess and map common failures to readable API errors."""
        try:
            completed = subprocess.run(
                ["git", *args],
                capture_output=True,
                check=False,
                text=True,
                cwd=str(cwd),
                timeout=60.0,
            )
        except FileNotFoundError as exc:
            raise WorkspaceServiceError(503, "Git is not installed on the host.") from exc
        except subprocess.TimeoutExpired as exc:
            raise WorkspaceServiceError(504, f"Git timed out while trying to {label}.") from exc
        except OSError as exc:
            raise WorkspaceServiceError(
                503,
                f"Failed to launch git while trying to {label}: {exc}",
            ) from exc

        if completed.returncode != 0:
            detail = self._normalize_git_error_detail(completed.stderr, completed.stdout, label)
            raise WorkspaceServiceError(self._status_code_for_git_error(detail), detail)
        return completed

    def _try_run_git(self, args: list[str], *, cwd: Path) -> str | None:
        """Run a git command and return stdout when it succeeds, otherwise None."""
        try:
            completed = subprocess.run(
                ["git", *args],
                capture_output=True,
                check=False,
                text=True,
                cwd=str(cwd),
                timeout=15.0,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return None

        if completed.returncode != 0:
            return None
        return completed.stdout

    def _run_gh(
        self,
        args: list[str],
        *,
        label: str,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run a gh subprocess and map failures to readable API errors."""
        try:
            completed = subprocess.run(
                ["gh", *args],
                capture_output=True,
                check=False,
                text=True,
                cwd=str(cwd) if cwd is not None else None,
                timeout=60.0,
            )
        except FileNotFoundError as exc:
            raise WorkspaceServiceError(503, "GitHub CLI is not installed on the host.") from exc
        except subprocess.TimeoutExpired as exc:
            raise WorkspaceServiceError(
                504,
                f"GitHub CLI timed out while trying to {label}.",
            ) from exc
        except OSError as exc:
            raise WorkspaceServiceError(
                503,
                f"Failed to launch GitHub CLI while trying to {label}: {exc}",
            ) from exc

        if completed.returncode != 0:
            detail = self._normalize_gh_error_detail(completed.stderr, completed.stdout, label)
            raise WorkspaceServiceError(self._status_code_for_gh_error(detail), detail)
        return completed

    def _view_pull_by_reference(self, repo_full_name: str, reference: str) -> dict[str, object]:
        """Resolve one PR by branch reference after a successful gh pr create call."""
        completed = self._run_gh(
            [
                "pr",
                "view",
                reference,
                "--repo",
                repo_full_name,
                "--json",
                "number,url",
            ],
            label="read created pull request",
        )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise WorkspaceServiceError(
                502,
                "GitHub CLI returned invalid JSON for pull request view.",
            ) from exc

        if not isinstance(payload, dict):
            raise WorkspaceServiceError(
                502,
                "GitHub CLI returned an unexpected pull request view payload.",
            )
        if not isinstance(payload.get("number"), int) or not isinstance(payload.get("url"), str):
            raise WorkspaceServiceError(
                502,
                "GitHub CLI returned incomplete pull request metadata.",
            )
        return payload

    @staticmethod
    def _build_remote_url(repo_url: str) -> str:
        """Convert a repo HTML URL to an HTTPS clone URL."""
        return repo_url if repo_url.endswith(".git") else f"{repo_url}.git"

    @staticmethod
    def _generate_working_branch(repo_name: str) -> str:
        """Generate a stable branch name for a prepared workspace."""
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%d%H%M%S")
        suffix = uuid.uuid4().hex[:6]
        normalized_repo = "".join(ch if ch.isalnum() or ch in "-_/" else "-" for ch in repo_name)
        return f"tap/{normalized_repo}/{timestamp}-{suffix}"

    @staticmethod
    def _parse_git_status(output: str) -> list[str]:
        """Parse porcelain git status output into a unique list of changed paths."""
        changed_files: list[str] = []
        seen: set[str] = set()
        for raw_line in output.splitlines():
            line = raw_line.rstrip()
            if len(line) < 4:
                continue
            path = line[3:].strip()
            if " -> " in path:
                path = path.split(" -> ", maxsplit=1)[1].strip()
            if path and path not in seen:
                seen.add(path)
                changed_files.append(path)
        return changed_files

    @staticmethod
    def _resolve_repo_file_path(*, repo_dir: Path, relative_path: str) -> Path:
        """Return a validated file path inside the repo root."""
        normalized = PurePosixPath(relative_path.strip())
        if not relative_path.strip():
            raise WorkspaceServiceError(400, "Workspace file path must not be empty.")
        if normalized.is_absolute():
            raise WorkspaceServiceError(400, "Workspace file path must be relative.")
        if any(part in {"", ".", ".."} for part in normalized.parts):
            raise WorkspaceServiceError(
                400,
                f"Workspace file path is not allowed: {relative_path}",
            )

        resolved = (repo_dir / Path(*normalized.parts)).resolve()
        try:
            resolved.relative_to(repo_dir.resolve())
        except ValueError as exc:
            raise WorkspaceServiceError(
                400,
                f"Workspace file path escapes the repo root: {relative_path}",
            ) from exc
        return resolved

    @staticmethod
    def _resolve_repo_directory_path(*, repo_dir: Path, relative_path: str) -> Path:
        """Return a validated directory path inside the repo root."""
        normalized = PurePosixPath(relative_path.strip())
        if normalized == PurePosixPath("."):
            return repo_dir.resolve()
        if normalized.is_absolute():
            raise WorkspaceServiceError(400, "Workspace directory path must be relative.")
        if any(part in {"", ".", ".."} for part in normalized.parts):
            raise WorkspaceServiceError(
                400,
                f"Workspace directory path is not allowed: {relative_path}",
            )

        resolved = (repo_dir / Path(*normalized.parts)).resolve()
        try:
            resolved.relative_to(repo_dir.resolve())
        except ValueError as exc:
            raise WorkspaceServiceError(
                400,
                f"Workspace directory path escapes the repo root: {relative_path}",
            ) from exc
        if not resolved.exists():
            raise WorkspaceServiceError(
                404,
                f"Workspace directory path does not exist: {relative_path}",
            )
        if not resolved.is_dir():
            raise WorkspaceServiceError(
                400,
                f"Workspace directory path is not a directory: {relative_path}",
            )
        return resolved

    @staticmethod
    def _normalize_git_error_detail(stderr: str, stdout: str, label: str) -> str:
        """Normalize git stderr/stdout into actionable API messages."""
        detail = (stderr or stdout).strip()
        normalized = detail.lower()
        if (
            "could not read username for 'https://github.com'" in normalized
            or "authentication failed" in normalized
            or "repository not found" in normalized
        ):
            return (
                "Git authentication failed while trying to "
                f"{label}. If `gh auth status` is ready, run `gh auth setup-git` "
                "or configure SSH access for this repository."
            )
        if "did not match any file(s) known to git" in normalized:
            return f"Git could not find the requested branch while trying to {label}."
        if "author identity unknown" in normalized:
            return (
                "Git user.name and user.email are not configured for commits. "
                "Run `git config --global user.name ...` and `git config --global user.email ...`."
            )
        if detail:
            return detail
        return f"Git command failed while trying to {label}."

    @staticmethod
    def _status_code_for_git_error(detail: str) -> int:
        """Map git failures to useful HTTP status codes."""
        normalized = detail.lower()
        if "branch" in normalized and "could not find" in normalized:
            return 404
        if "authentication failed" in normalized or "repository not found" in normalized:
            return 503
        if "author identity unknown" in normalized:
            return 409
        return 502

    @staticmethod
    def _normalize_gh_error_detail(stderr: str, stdout: str, label: str) -> str:
        """Normalize gh stderr/stdout into actionable API messages."""
        detail = (stderr or stdout).strip()
        if detail:
            return detail
        return f"GitHub CLI request failed while trying to {label}."

    @staticmethod
    def _status_code_for_gh_error(detail: str) -> int:
        """Map gh failures to useful HTTP status codes."""
        normalized = detail.lower()
        if (
            "not logged into any github hosts" in normalized
            or "authentication failed" in normalized
        ):
            return 503
        if "could not resolve to a repository" in normalized:
            return 404
        if "already exists" in normalized or "no commits between" in normalized:
            return 409
        return 502


def _utc_now() -> str:
    """Return a stable ISO timestamp in UTC."""
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
