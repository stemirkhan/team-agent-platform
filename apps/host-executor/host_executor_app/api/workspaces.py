"""Workspace lifecycle endpoints backed by host git and gh subprocesses."""

from fastapi import APIRouter, HTTPException, Path, status

from host_executor_app.schemas.workspace import (
    WorkspaceCommit,
    WorkspaceListResponse,
    WorkspaceMaterialize,
    WorkspacePrepare,
    WorkspacePullRequestCreate,
    WorkspaceRead,
)
from host_executor_app.services.workspace_service import WorkspaceService, WorkspaceServiceError

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
workspace_service = WorkspaceService()


@router.get("", response_model=WorkspaceListResponse)
def list_workspaces() -> WorkspaceListResponse:
    """Return all persisted local workspaces."""
    return workspace_service.list_workspaces()


@router.post("/prepare", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
def prepare_workspace(payload: WorkspacePrepare) -> WorkspaceRead:
    """Prepare a new local workspace by cloning a repo and creating a branch."""
    try:
        return workspace_service.prepare_workspace(payload)
    except WorkspaceServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/{workspace_id}", response_model=WorkspaceRead)
def get_workspace(workspace_id: str = Path(min_length=1)) -> WorkspaceRead:
    """Return one workspace with refreshed git state."""
    try:
        return workspace_service.get_workspace(workspace_id)
    except WorkspaceServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/{workspace_id}/commit", response_model=WorkspaceRead)
def commit_workspace(
    payload: WorkspaceCommit,
    workspace_id: str = Path(min_length=1),
) -> WorkspaceRead:
    """Commit local changes inside an existing workspace."""
    try:
        return workspace_service.commit_workspace(workspace_id, payload)
    except WorkspaceServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/{workspace_id}/materialize", response_model=WorkspaceRead)
def materialize_workspace(
    payload: WorkspaceMaterialize,
    workspace_id: str = Path(min_length=1),
) -> WorkspaceRead:
    """Write text files into a prepared workspace."""
    try:
        return workspace_service.materialize_workspace(workspace_id, payload)
    except WorkspaceServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/{workspace_id}/cleanup", response_model=WorkspaceRead)
def cleanup_workspace(workspace_id: str = Path(min_length=1)) -> WorkspaceRead:
    """Restore or delete temporary run scaffolding files inside a workspace."""
    try:
        return workspace_service.cleanup_materialized_files(workspace_id)
    except WorkspaceServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/{workspace_id}/push", response_model=WorkspaceRead)
def push_workspace(workspace_id: str = Path(min_length=1)) -> WorkspaceRead:
    """Push the workspace branch to origin."""
    try:
        return workspace_service.push_workspace(workspace_id)
    except WorkspaceServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/{workspace_id}/pull-request", response_model=WorkspaceRead)
def create_workspace_pull_request(
    payload: WorkspacePullRequestCreate,
    workspace_id: str = Path(min_length=1),
) -> WorkspaceRead:
    """Create a draft or ready pull request from a pushed workspace branch."""
    try:
        return workspace_service.create_pull_request(workspace_id, payload)
    except WorkspaceServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace(workspace_id: str = Path(min_length=1)) -> None:
    """Delete a persisted workspace directory."""
    try:
        workspace_service.delete_workspace(workspace_id)
    except WorkspaceServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
