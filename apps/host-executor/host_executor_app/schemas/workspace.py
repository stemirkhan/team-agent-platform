"""Schemas for host workspace lifecycle and git/GitHub write-side operations."""

from typing import Literal

from pydantic import BaseModel, Field

WorkspaceStatus = Literal["prepared", "committed", "pushed", "pull_request_created"]


class WorkspaceRead(BaseModel):
    """Normalized workspace payload returned by the host executor."""

    id: str
    repo_owner: str
    repo_name: str
    repo_full_name: str
    remote_url: str
    workspace_path: str
    repo_path: str
    base_branch: str
    working_branch: str
    current_branch: str | None = None
    upstream_branch: str | None = None
    status: WorkspaceStatus
    has_changes: bool = False
    changed_files: list[str] = Field(default_factory=list)
    initial_head_sha: str | None = None
    initial_head_message: str | None = None
    last_commit_sha: str | None = None
    last_commit_message: str | None = None
    committed_at: str | None = None
    pushed_at: str | None = None
    pull_request_number: int | None = None
    pull_request_url: str | None = None
    created_at: str
    updated_at: str


class WorkspaceListResponse(BaseModel):
    """Paginated workspace list."""

    items: list[WorkspaceRead] = Field(default_factory=list)
    total: int


class WorkspacePrepare(BaseModel):
    """Payload for preparing a new workspace from a repository target."""

    owner: str = Field(min_length=1, max_length=255)
    repo: str = Field(min_length=1, max_length=255)
    base_branch: str | None = Field(default=None, min_length=1, max_length=255)
    working_branch: str | None = Field(default=None, min_length=1, max_length=255)


class WorkspaceCommit(BaseModel):
    """Payload for committing workspace changes."""

    message: str = Field(min_length=1, max_length=500)


class WorkspacePullRequestCreate(BaseModel):
    """Payload for creating a draft pull request from a prepared workspace."""

    title: str = Field(min_length=1, max_length=255)
    body: str | None = Field(default=None, max_length=20000)
    draft: bool = True


class WorkspaceFileWrite(BaseModel):
    """One text file that should be written under the workspace repo root."""

    path: str = Field(min_length=1, max_length=1000)
    content: str = Field(default="", max_length=500_000)


class WorkspaceMaterialize(BaseModel):
    """Batch of files to materialize inside a prepared workspace."""

    files: list[WorkspaceFileWrite] = Field(default_factory=list, min_length=1, max_length=500)


class WorkspaceCommandsRun(BaseModel):
    """Batch of shell commands that should run inside one prepared workspace."""

    commands: list[str] = Field(default_factory=list, min_length=1, max_length=50)
    working_directory: str = Field(default=".", min_length=1, max_length=1000)
    label: str | None = Field(default=None, max_length=255)


class WorkspaceCommandResult(BaseModel):
    """One command execution result inside a workspace."""

    command: str
    exit_code: int
    output: str
    started_at: str
    finished_at: str
    succeeded: bool


class WorkspaceCommandsRunResponse(BaseModel):
    """Result of sequential workspace command execution."""

    label: str | None = None
    working_directory: str
    success: bool
    failed_command: str | None = None
    items: list[WorkspaceCommandResult] = Field(default_factory=list)
